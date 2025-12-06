"""Bot service - runs the Kafka consumer and message processing."""
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
from rate_limit_checker import record_message_sent, get_rate_limit_status
from contact_manager import get_contact_name, get_contact_by_phone, update_contact_info, add_contact_from_message, sync_from_macos_contacts
from conversation_tracker import add_message, has_replied, get_conversation_thread, get_conversation_summary
from next_message_generator import generate_next_message, generate_follow_up_message
from decision_support import analyze_conversation_state, should_send_message
from guardrails import (
    check_content_safety, check_rate_limit, record_message, check_user_status,
    flag_user, record_violation, validate_response, sanitize_input
)
from agent_orchestrator import process_user_request
from permission_manager import (
    check_contact_permission, request_contact_permission,
    process_permission_response, grant_contact_permission, deny_contact_permission
)
from pending_actions import (
    set_pending_confirmation, get_pending_confirmation, clear_pending_confirmation,
    set_pending_details, get_pending_details, clear_pending_details, is_confirmation_response
)
from reminder_scheduler import start_reminder_scheduler
from meeting_checker import get_meetings_and_emails_summary

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
# Reminder Scheduler Callback
# =========================
def send_reminder_callback(message: str):
    """Callback function to send reminder messages via the bot."""
    try:
        from series_api import create_chat
        
        # Get recipient number from environment
        recipient_number = os.getenv("RECIPIENT_NUMBER", "+12017056654")
        
        # Format recipient number (ensure +1 prefix)
        if not recipient_number.startswith("+"):
            if recipient_number.startswith("1") and len(recipient_number) == 11:
                recipient_number = f"+{recipient_number}"
            elif len(recipient_number) == 10:
                recipient_number = f"+1{recipient_number}"
        
        # Create chat with recipient number and send reminder
        create_chat(
            phone_numbers=[recipient_number],
            message_text=message,
            display_name="Meeting Reminder"
        )
        print(f"[Bot] 📅 Reminder sent to {recipient_number}: {message[:50]}...")
    except Exception as e:
        print(f"[Bot] ❌ Error sending reminder: {e}")
        import traceback
        traceback.print_exc()

# Start reminder scheduler with AI client for smart email classification
try:
    start_reminder_scheduler(send_reminder_callback, ai_client)
    print("[Bot] ✅ Reminder scheduler started with AI email classification")
except Exception as e:
    print(f"[Bot] ⚠️  Could not start reminder scheduler: {e}")
    print("[Bot] ℹ️  Meeting reminders will not be available")

# =========================
# Main Message Processing Loop
# =========================
def run_bot():
    """Run the bot service - processes Kafka messages."""
    print("[Bot] Starting PingHumans bot service...")
    
    # Sync contacts from macOS Contacts app on startup
    try:
        print("[Bot] Syncing contacts from macOS Contacts app...")
        synced_count = sync_from_macos_contacts()
        if synced_count > 0:
            print(f"[Bot] ✅ Loaded {synced_count} contacts from macOS Contacts app")
        else:
            print("[Bot] ℹ️  No contacts synced from macOS (will use contacts from iMessage)")
    except Exception as e:
        print(f"[Bot] ⚠️  Could not sync macOS contacts: {e}")
        print("[Bot] ℹ️  Will use contacts from iMessage data instead")
    
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
                    
                    # Extract contacts from iMessage data (chat_handles)
                    chat_handles = data.get("chat_handles", [])
                    for handle in chat_handles:
                        phone = handle.get("identifier")
                        display_name = handle.get("display_name", phone)
                        is_me = handle.get("is_me", False)
                        
                        if phone and not is_me:
                            # Add contact from iPhone message data (iPhone permission - contacts from iMessage)
                            from datetime import datetime
                            contact = add_contact_from_message(phone, text, str(chat_id))
                            # Update with display name from iPhone
                            if display_name and display_name != phone:
                                update_contact_info(phone, {
                                    "name": display_name,
                                    "display_name": display_name,
                                    "phone_number": phone,
                                    "source": "iphone_message",
                                    "last_seen": datetime.now().isoformat()
                                })
                                print(f"[Bot] 📱 Extracted contact from iPhone: {display_name} ({phone})")

                    # Skip empty messages
                    if not text:
                        continue

                    # =========================
                    # PENDING CONFIRMATION/DETAILS CHECK (BEFORE permission check)
                    # =========================
                    # Check if there's a pending confirmation first
                    pending_confirmation = get_pending_confirmation(str(chat_id))
                    if pending_confirmation and is_confirmation_response(text):
                        # User confirmed, now ask for order details
                        action_type = pending_confirmation.get("action", "order")
                        contact_info = pending_confirmation.get("contact", {})
                        contact_name = contact_info.get("name", "Unknown")
                        
                        # Ask for order details
                        if action_type == "order":
                            reply_text = f"✅ Great! I found '{contact_name}' in your contacts.\n\n📝 Please provide order details:\n• What would you like to order? (e.g., pizza type)\n• Size/quantity?\n• Any special instructions?"
                        else:
                            reply_text = f"✅ Great! I found '{contact_name}' in your contacts.\n\n📝 Please provide details for your {action_type} request:"
                        
                        # Set pending details collection
                        set_pending_details(str(chat_id), {
                            "action": action_type,
                            "contact": contact_info,
                            "original_request": pending_confirmation.get("original_request", "")
                        })
                        clear_pending_confirmation(str(chat_id))
                        
                        send_message(int(chat_id), reply_text)
                        add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                        record_message_sent()
                        record_response()
                        continue
                    
                    # =========================
                    # PERMISSION RESPONSE CHECK (after pending actions)
                    # =========================
                    # Only check permission if there's no pending action
                    # Check if this is a response to a permission request
                    permission_response = process_permission_response(text, str(chat_id), sender)
                    if permission_response:
                        if permission_response.get("granted"):
                            reply_text = permission_response.get("message", "✅ Contact access granted!")
                            print(f"[Bot] ✅ Permission granted by user")
                        else:
                            reply_text = permission_response.get("message", "Contact access denied.")
                            print(f"[Bot] ❌ Permission denied by user")
                        
                        send_message(int(chat_id), reply_text)
                        add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                        record_message_sent()
                        record_response()
                        continue  # Skip normal processing
                    
                    # Check if there's pending details collection
                    pending_detail = get_pending_details(str(chat_id))
                    if pending_detail:
                        # User provided details, now execute the action
                        from action_executor import execute_action
                        
                        action_type = pending_detail.get("action", "order")
                        contact_info = pending_detail.get("contact", {})
                        original_request = pending_detail.get("original_request", "")
                        
                        # Debug: Print contact info
                        print(f"[Bot] 🔍 Executing {action_type} action")
                        print(f"[Bot] 🔍 Contact info: {json.dumps(contact_info, indent=2)}")
                        print(f"[Bot] 🔍 Contact name: {contact_info.get('name')}")
                        print(f"[Bot] 🔍 Contact phone: {contact_info.get('phone_number')}")
                        print(f"[Bot] 🔍 Original request: {original_request}")
                        print(f"[Bot] 🔍 User details: {text}")
                        
                        # Verify contact has phone number
                        if not contact_info.get("phone_number") and not contact_info.get("phone"):
                            print(f"[Bot] ❌ Contact missing phone number!")
                            reply_text = f"❌ Error: Contact '{contact_info.get('name', 'Unknown')}' doesn't have a phone number. Cannot send order."
                            send_message(int(chat_id), reply_text)
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            clear_pending_details(str(chat_id))
                            continue
                        
                        # Combine original request with user's details
                        full_request = f"{original_request}. Details: {text}"
                        
                        # Execute the action
                        try:
                            result = execute_action(action_type, full_request, contact_info, str(chat_id), ai_client)
                            
                            print(f"[Bot] 🔍 Action result: {result}")
                            
                            if result.get("success"):
                                contact_name = contact_info.get("name") or contact_info.get("display_name", "Unknown")
                                sent_msg = result.get('sent_message', '')
                                reply_text = f"✅ Order sent to {contact_name}!\n\n📨 Message sent:\n{sent_msg[:200]}"
                                print(f"[Bot] ✅ Order sent successfully to {contact_name}")
                            else:
                                error_msg = result.get('message', 'Unknown error')
                                error_detail = result.get('error', '')
                                reply_text = f"❌ Failed to send order: {error_msg}"
                                if error_detail:
                                    reply_text += f"\n\nError: {error_detail}"
                                print(f"[Bot] ❌ Failed to send order: {error_msg}")
                                print(f"[Bot] ❌ Error details: {error_detail}")
                            
                            clear_pending_details(str(chat_id))
                            
                            send_message(int(chat_id), reply_text)
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            record_message_sent()
                            record_response()
                            continue
                        except Exception as e:
                            import traceback
                            print(f"[Bot] ❌ Error executing action: {e}")
                            print(f"[Bot] ❌ Traceback: {traceback.format_exc()}")
                            clear_pending_details(str(chat_id))
                            # Send error message to user
                            reply_text = f"❌ Error sending order: {str(e)}. Please try again."
                            send_message(int(chat_id), reply_text)
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            record_message_sent()
                            record_response()
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
                        can_send, limit_reason = check_rate_limit(sender)
                        if not can_send:
                            print(f"[Bot] ⚠️  Rate limit check: {limit_reason}")
                            print(f"[Bot] Message received and processed, but reply blocked by rate limit.")
                            # Still update analytics for received message
                            continue
                        
                        # =========================
                        # CHECK FOR MEETING/EMAIL QUERIES
                        # =========================
                        text_lower = text.lower().strip()
                        meeting_keywords = ["meeting", "meetings", "appointment", "appointments", "calendar", "schedule"]
                        email_keywords = ["urgent", "email", "emails", "mail", "mails", "inbox"]
                        is_meeting_query = any(keyword in text_lower for keyword in meeting_keywords)
                        is_email_query = any(keyword in text_lower for keyword in email_keywords)
                        
                        if is_meeting_query or is_email_query:
                            print(f"[Bot] 📅 Detected meeting/email query, checking Gmail/Calendar...")
                            try:
                                summary = get_meetings_and_emails_summary()
                                reply_text = summary
                                
                                send_message(int(chat_id), reply_text)
                                add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                record_message_sent()
                                record_response()
                                continue  # Skip normal processing
                            except Exception as e:
                                print(f"[Bot] ❌ Error checking meetings/emails: {e}")
                                import traceback
                                traceback.print_exc()
                                # Fall through to normal response
                        
                        # =========================
                        # MULTI-AGENT SYSTEM: Check if request needs contact-based action
                        # =========================
                        # Check if this is an actionable request (order, book, call, etc.)
                        # Also check for direct item requests (e.g., "margaritas", "pizza", "artichoke")
                        action_keywords = ["order", "buy", "book", "schedule", "call", "contact", "find", "get me", "get", "want", "need"]
                        is_actionable = any(keyword in text_lower for keyword in action_keywords)
                        
                        # Also check if message starts with item names (common ordering pattern)
                        # If user says "margaritas" or "artichoke" after previous order context, treat as actionable
                        if not is_actionable:
                            # Check conversation history for order context
                            from conversation_tracker import get_conversation_thread
                            thread = get_conversation_thread(str(chat_id), limit=5)
                            recent_context = " ".join([msg.get("text", "").lower() for msg in thread[-3:]])
                            if "order" in recent_context or any(word in recent_context for word in ["pizza", "food", "restaurant", "delivery"]):
                                # User might be providing order details or ordering items
                                is_actionable = True
                                print(f"[Bot] 🔍 Detected actionable request from conversation context")
                        
                        if is_actionable:
                            print(f"[Bot] 🤖 Detected actionable request, processing with multi-agent system...")
                            try:
                                agent_result = process_user_request(text, str(chat_id), sender, ai_client)
                                
                                if agent_result.get("needs_permission"):
                                    # Permission required
                                    reply_text = agent_result.get("message", "Permission required to access contacts")
                                    print(f"[Bot] 🔐 Permission required for contact access")
                                elif agent_result.get("success"):
                                    # Action executed successfully
                                    reply_text = f"✅ {agent_result.get('message', 'Action completed')}"
                                    if agent_result.get("sent_message"):
                                        reply_text += f"\n\nSent: {agent_result.get('sent_message', '')[:100]}..."
                                    print(f"[Bot] ✅ Agent action successful: {agent_result.get('action')} with {agent_result.get('contact')}")
                                else:
                                    # Action failed or needs confirmation
                                    if agent_result.get("needs_confirmation"):
                                        contact_info = agent_result.get("contact", {})
                                        contact_name = contact_info.get("name") or contact_info.get("display_name", "Unknown")
                                        action_type = agent_result.get("action", "order")
                                        
                                        # Set pending confirmation
                                        set_pending_confirmation(str(chat_id), {
                                            "action": action_type,
                                            "contact": contact_info,
                                            "original_request": text
                                        })
                                        
                                        reply_text = f"✅ I found '{contact_name}' in your contacts. Should I proceed with {action_type}? (Reply 'yes' to continue)"
                                    else:
                                        # Use the specific error message from agent (e.g., "No contact named 'pizza' or 'pizza guy' found")
                                        reply_text = agent_result.get("message", "I couldn't complete that action. How else can I help?")
                                    
                                    print(f"[Bot] ⚠️  Agent action result: {agent_result.get('message')}")
                                
                                # Send the response
                                send_message(int(chat_id), reply_text)
                                add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                record_message_sent()
                                record_response()
                                continue  # Skip normal response generation
                                
                            except Exception as e:
                                print(f"[Bot] ⚠️  Agent system error: {e}, falling back to normal response")
                                import traceback
                                traceback.print_exc()
                                # Fall through to normal response generation
                        
                        # Generate AI response with context (normal flow)
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

