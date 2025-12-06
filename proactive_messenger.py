"""Proactive messaging functionality."""
import time
from datetime import datetime, timedelta
from openai import OpenAI
from series_api import send_message

# Track last message time per chat for proactive messaging
last_message_time = {}
PROACTIVE_DELAY_MINUTES = 30  # Send proactive message after 30 min of inactivity

def update_last_message_time(chat_id: str):
    """Update the last message time for a chat."""
    last_message_time[chat_id] = datetime.now().isoformat()

def check_proactive_messaging(conversation_history: dict, ai_client: OpenAI):
    """Check if we should send proactive messages to inactive chats."""
    if not ai_client:
        return
    
    current_time = datetime.now()
    
    for chat_id, last_time in list(last_message_time.items()):
        if isinstance(last_time, str):
            try:
                last_time = datetime.fromisoformat(last_time)
            except:
                continue
        
        time_diff = current_time - last_time
        if time_diff > timedelta(minutes=PROACTIVE_DELAY_MINUTES):
            # Check if we've already sent a proactive message recently
            if chat_id in conversation_history:
                last_assistant_msg = None
                for msg in reversed(conversation_history[chat_id]):
                    if msg["role"] == "assistant":
                        last_assistant_msg = msg["content"]
                        break
                
                # Only send if last message wasn't already proactive
                if last_assistant_msg and "just checking in" not in last_assistant_msg.lower():
                    try:
                        # Get user's language preference from ai_responder
                        from ai_responder import user_languages
                        user_lang = user_languages.get(chat_id, "en")
                        
                        # Generate proactive message in user's language
                        if user_lang != "en":
                            from language_detector import get_language_name
                            lang_name = get_language_name(user_lang)
                            
                            response = ai_client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[
                                    {"role": "system", "content": f"Translate this message to {lang_name} ({user_lang}). Keep it friendly and casual."},
                                    {"role": "user", "content": "Hey! Just checking in - is there anything I can help you with?"}
                                ],
                                temperature=0.5,
                                max_tokens=50
                            )
                            proactive_msg = response.choices[0].message.content.strip()
                        else:
                            proactive_msg = "Hey! Just checking in - is there anything I can help you with?"
                        
                        send_message(int(chat_id), proactive_msg)
                        print(f"[Proactive] Sent message to chat {chat_id} in {user_lang}")
                        last_message_time[chat_id] = current_time.isoformat()
                    except Exception as e:
                        print(f"[Proactive] Failed proactive message: {e}")

def start_proactive_loop(conversation_history: dict, ai_client: OpenAI):
    """Start the proactive messaging background loop."""
    from threading import Thread
    
    def proactive_loop():
        """Background thread for proactive messaging."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                check_proactive_messaging(conversation_history, ai_client)
            except Exception as e:
                print(f"[Proactive] Error: {e}")
    
    thread = Thread(target=proactive_loop, daemon=True)
    thread.start()
    print("[Proactive] Proactive messaging enabled (checks every minute)")

