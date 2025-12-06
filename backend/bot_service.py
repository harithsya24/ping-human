"""Bot service - runs the Kafka consumer and message processing."""
import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI

# Import all functionality modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kafka_consumer import create_consumer
from series_api import send_message
from sentiment_analyzer import analyze_message
from ai_responder import generate_response, generate_summary, conversation_history
from analytics import update_analytics, record_response, print_analytics
from proactive_messenger import update_last_message_time, start_proactive_loop
from language_detector import get_language_name
from rate_limit_checker import check_rate_limit, record_message_sent, get_rate_limit_status
from contact_manager import get_contact_name, get_contact_by_phone, update_contact_info
from conversation_tracker import add_message, has_replied, get_conversation_thread, get_conversation_summary
from next_message_generator import generate_next_message, generate_follow_up_message
from decision_support import analyze_conversation_state, should_send_message
from guardrails import (
    check_content_safety, check_rate_limit, record_message, check_user_status,
    flag_user, record_violation, validate_response, sanitize_input
)

load_dotenv()

# =========================
# ENVIRONMENT VARIABLES
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
def run_bot():
    """Run the bot service - processes Kafka messages."""
    print("[Bot] Starting PingHumans bot service...")
    
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

                    # =========================
                    # GUARDRAILS: Input Validation
                    # =========================
                    # Check if user is blocked
                    user_status = check_user_status(sender)
                    if not user_status.get("allowed", True):
                        print(f"[Bot] 🚫 Message from {sender} blocked: {user_status.get('reason', 'unknown')}")
                        record_violation(sender, "blocked_user_attempt", {"chat_id": chat_id})
                        continue
                    
                    # Check rate limits
                    rate_ok, rate_reason = check_rate_limit(sender)
                    if not rate_ok:
                        print(f"[Bot] 🚫 Rate limit exceeded for {sender}: {rate_reason}")
                        record_violation(sender, "rate_limit_exceeded", {"reason": rate_reason})
                        continue
                    
                    # Sanitize input
                    text = sanitize_input(text)
                    
                    # Check content safety
                    safety_check = check_content_safety(text, ai_client)
                    if not safety_check.get("safe", True):
                        print(f"[Bot] 🚫 Unsafe content from {sender}: {safety_check.get('message', 'unknown')}")
                        record_violation(sender, safety_check.get("reason", "unsafe_content"), safety_check)
                        flag_user(sender, safety_check.get("reason", "unsafe_content"), safety_check.get("severity", "medium"))
                        continue
                    
                    # Record message for rate limiting
                    record_message(sender)

                    # Get contact information
                    contact = get_contact_by_phone(sender)
                    contact_name = contact.get("name") or contact.get("display_name") if contact else sender
                    
                    print(f"[Bot] New message in chat {chat_id} from {contact_name} ({sender}): {text}")

                    # Track message in conversation thread
                    add_message(str(chat_id), sender, text, message_id, is_bot=False)
                    
                    # Check if this is a reply
                    has_replied_recently = has_replied(str(chat_id), sender, within_minutes=60)
                    if has_replied_recently:
                        print(f"[Bot] 📨 User {contact_name} has replied within the last hour")

                    # Analyze message for sentiment, intent, and language
                    analysis = analyze_message(text, ai_client)
                    sentiment = analysis.get("sentiment", "neutral")
                    intent = analysis.get("intent", "general")
                    urgency = analysis.get("urgency", "medium")
                    language = analysis.get("language", "en")
                    
                    lang_display = get_language_name(language)
                    print(f"[Bot] Analysis - Language: {lang_display} ({language}), Sentiment: {sentiment}, Intent: {intent}, Urgency: {urgency}")

                    # Update contact info with latest interaction
                    if contact:
                        from datetime import datetime
                        update_contact_info(sender, {
                            "last_message": text,
                            "last_message_time": datetime.now().isoformat(),
                            "preferred_language": language
                        })

                    # Update analytics
                    update_analytics(sender, text, analysis)
                    
                    # Update last message time for proactive messaging
                    update_last_message_time(str(chat_id))
                    
                    # Analyze conversation state for decision support
                    conversation_state = analyze_conversation_state(str(chat_id), ai_client)
                    print(f"[Bot] Conversation state: {conversation_state.get('recommendation')} (priority: {conversation_state.get('priority')})")

                    # Generate AI response with context
                    try:
                        # Check rate limits before sending
                        can_send, limit_reason = check_rate_limit()
                        if not can_send:
                            print(f"[Bot] ⚠️  Rate limit check: {limit_reason}")
                            print(f"[Bot] Message received and processed, but reply blocked by rate limit.")
                            # Still update analytics for received message
                            continue
                        
                        # Generate AI response with context
                        reply_text = generate_response(text, str(chat_id), sender, analysis, ai_client)
                        
                        # =========================
                        # GUARDRAILS: Response Validation
                        # =========================
                        response_validation = validate_response(reply_text, ai_client)
                        if not response_validation.get("valid", True):
                            print(f"[Bot] 🚫 Response validation failed: {response_validation.get('message', 'unknown')}")
                            # Generate a safe fallback response
                            reply_text = "I apologize, but I'm unable to provide a response to that. How else can I help you?"
                        
                        # Track bot message in conversation thread
                        send_message(int(chat_id), reply_text)
                        add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                        
                        record_message_sent()  # Track for rate limiting
                        record_response()
                        print(f"[Bot] ✅ Sent AI reply: {reply_text}")
                        
                        # Log conversation summary
                        summary = get_conversation_summary(str(chat_id))
                        print(f"[Bot] 📊 Conversation summary: {summary['message_count']} messages, {len(summary['participants'])} participants")
                        
                        # Special handling for summary requests
                        if "summary" in text.lower() or "summarize" in text.lower():
                            summary = generate_summary(str(chat_id), ai_client)
                            send_message(int(chat_id), f"📋 Conversation Summary: {summary}")
                            print(f"[Bot] ✅ Sent summary for chat {chat_id}")
                        
                        # Print analytics every 5 messages
                        if message_count % 5 == 0:
                            print_analytics()
                            
                    except Exception as e:
                        error_msg = str(e)
                        if "Rate limit" in error_msg or "429" in error_msg:
                            print(f"[Bot] ⚠️  RATE LIMIT HIT! Message received but cannot reply.")
                            print(f"[Bot] This might be due to organizer-set limits. Message was still processed.")
                        elif "Quota" in error_msg or "403" in error_msg:
                            print(f"[Bot] ⚠️  QUOTA EXCEEDED! Message received but cannot reply.")
                            print(f"[Bot] Check if you've hit the message limit set by organizers.")
                        else:
                            print(f"[Bot] ❌ Failed to send reply: {e}")
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

if __name__ == '__main__':
    run_bot()

