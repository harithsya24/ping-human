"""Main entry point for PingHumans - orchestrates all functionality."""
import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI

# Import all functionality modules
from kafka_consumer import create_consumer
from series_api import send_message
from sentiment_analyzer import analyze_message
from ai_responder import generate_response, generate_summary, conversation_history
from analytics import update_analytics, record_response, print_analytics
from proactive_messenger import update_last_message_time, start_proactive_loop
from language_detector import get_language_name

load_dotenv()

# =========================
# ENVIRONMENT VARIABLES
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("[Bot] Warning: OPENAI_API_KEY not set, will use simple replies")

# =========================
# Initialize OpenAI Client
# =========================
ai_client = None
if OPENAI_API_KEY:
    ai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("[Bot] OpenAI client initialized")
else:
    print("[Bot] Warning: OPENAI_API_KEY not set, will use simple replies")

# Start proactive messaging
start_proactive_loop(conversation_history, ai_client)

# =========================
# Main Message Processing Loop
# =========================
print("[Bot] Starting PingHumans bot...")

# Main loop with reconnection
while True:
    consumer = None
    try:
        consumer = create_consumer()
        print("[Bot] Connected to Kafka, waiting for messages...")
        
        # Check partition assignment
        time.sleep(2)  # Wait a bit for partition assignment
        partitions = consumer.assignment()
        if partitions:
            print(f"[Bot] Assigned partitions: {[f'{p.topic}:{p.partition}' for p in partitions]}")
        else:
            print("[Bot] No partitions assigned yet - will receive when messages arrive")
        
        print("[Bot] Ready! Send a message to +16463769330 to test.")
        message_count = 0
        
        for msg in consumer:
            message_count += 1
            print(f"[Bot] === Message #{message_count} received ===")
            event = msg.value
            event_type = event.get("event_type")
            print(f"[Bot] Received message from partition {msg.partition}, offset {msg.offset}")
            print("[DEBUG] Raw Kafka event:", json.dumps(event, indent=2))
            data = event.get("data", {})

            # ------------------------
            # Message Received
            # ------------------------
            if event_type == "message.received":
                chat_id = data.get("chat_id")
                text = data.get("text", "").strip()
                sender = data.get("from_phone")
                message_id = data.get("id")

                # Skip empty messages
                if not text:
                    continue

                print(f"[Bot] New message in chat {chat_id} from {sender}: {text}")

                # Analyze message for sentiment, intent, and language
                analysis = analyze_message(text, ai_client)
                sentiment = analysis.get("sentiment", "neutral")
                intent = analysis.get("intent", "general")
                urgency = analysis.get("urgency", "medium")
                language = analysis.get("language", "en")
                
                lang_display = get_language_name(language)
                print(f"[Bot] Analysis - Language: {lang_display} ({language}), Sentiment: {sentiment}, Intent: {intent}, Urgency: {urgency}")

                # Update analytics
                update_analytics(sender, text, analysis)
                
                # Update last message time for proactive messaging
                update_last_message_time(str(chat_id))

                # Generate AI response with context
                try:
                    reply_text = generate_response(text, str(chat_id), sender, analysis, ai_client)
                    send_message(int(chat_id), reply_text)
                    record_response()
                    print(f"[Bot] Sent AI reply: {reply_text}")
                    
                    # Special handling for summary requests
                    if "summary" in text.lower() or "summarize" in text.lower():
                        summary = generate_summary(str(chat_id), ai_client)
                        send_message(int(chat_id), f"📋 Conversation Summary: {summary}")
                        print(f"[Bot] Sent summary for chat {chat_id}")
                    
                    # Print analytics every 5 messages
                    if message_count % 5 == 0:
                        print_analytics()
                        
                except Exception as e:
                    print(f"[Bot] Failed to send reply: {e}")
                    import traceback
                    traceback.print_exc()

            # ------------------------
            # Typing indicator events
            # ------------------------
            elif event_type in ["typing_indicator.received", "typing_indicator.removed"]:
                display = data.get("display")
                handles = data.get("chat_handles", [])
                print(f"[Bot] Typing event: {event_type}, display={display}")

    except KeyboardInterrupt:
        print("[Bot] Stopped by user.")
        break
    except Exception as e:
        print(f"[Bot] Connection error: {e}")
        print("[Bot] Reconnecting in 5 seconds...")
        if consumer:
            try:
                consumer.close()
            except:
                pass
        time.sleep(5)
    finally:
        if consumer:
            try:
                consumer.close()
            except:
                pass
