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
from action_history import log_action
from memory_retrieval import is_memory_retrieval_request, process_memory_request
from follow_up_scheduler import start_follow_up_scheduler, check_for_reply
from location_handler import is_location_message, process_location_message

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
    """Callback function to send reminder messages via the bot. STRICT: Only sends to allowed recipient."""
    try:
        from series_api import create_chat
        from messaging_rules import get_allowed_recipient
        
        recipient_number = get_allowed_recipient()
        
        create_chat(
            phone_numbers=[recipient_number],
            message_text=message,
            display_name="Meeting Reminder",
            enforce_recipient=True
        )
        print(f"[Bot] Reminder sent to {recipient_number}: {message[:50]}...")
    except Exception as e:
        print(f"[Bot] ERROR: Error sending reminder: {e}")
        import traceback
        traceback.print_exc()

# Start reminder scheduler with AI client for smart email classification
try:
    start_reminder_scheduler(send_reminder_callback, ai_client)
    print("[Bot] SUCCESS: Reminder scheduler started with AI email classification")
except Exception as e:
    print(f"[Bot] WARNING: Could not start reminder scheduler: {e}")
    print("[Bot] [INFO] Meeting reminders will not be available")

# =========================
# Follow-Up Scheduler Callback
# =========================
def send_follow_up_callback(recipient_phone: str, message: str, chat_id: str):
    """Callback function to send follow-up messages from the user (not the bot)."""
    try:
        from series_api import create_chat
        import os
        
        # Get user's phone number (SENDER_NUMBER) - this is the user's number
        sender_number = os.getenv("SENDER_NUMBER")
        if not sender_number:
            print("[Bot] WARNING: SENDER_NUMBER not set, cannot send follow-up from user")
            return
        
        recipient = recipient_phone
        if not recipient.startswith("+"):
            if recipient.startswith("1") and len(recipient) == 11:
                recipient = f"+{recipient}"
            elif len(recipient) == 10:
                recipient = f"+1{recipient}"
        
        # Send message from user's number (SENDER_NUMBER) to the friend
        # The create_chat function uses send_from which is set to SENDER_NUMBER
        # This makes the message appear as if it's from the user, not the bot
        create_chat(
            phone_numbers=[recipient],
            message_text=message,
            display_name=None,  # Use default display name
            enforce_recipient=False
        )
        print(f"[Bot] Follow-up sent from user ({sender_number}) to {recipient}: {message[:50]}...")
    except Exception as e:
        print(f"[Bot] ERROR: Error sending follow-up: {e}")
        import traceback
        traceback.print_exc()
        import traceback
        traceback.print_exc()

# Start follow-up scheduler
try:
    start_follow_up_scheduler(send_follow_up_callback)
    print("[Bot] SUCCESS: Follow-up scheduler started")
except Exception as e:
    print(f"[Bot] WARNING: Could not start follow-up scheduler: {e}")
    print("[Bot] [INFO] Follow-up messages will not be available")

# =========================
# Main Message Processing Loop
# =========================
def run_bot():
    """Run the bot service - processes Kafka messages."""
    print("[Bot] Starting PingHumans bot service...")
    
    # Sync contacts from macOS Contacts app on startup (only if cache doesn't exist)
    try:
        from contact_manager import CONTACTS_JSON_FILE
        import os
        if os.path.exists(CONTACTS_JSON_FILE):
            print(f"[Bot] INFO: Contacts cache exists ({CONTACTS_JSON_FILE}), skipping macOS sync")
            print("[Bot] INFO: Using cached contacts. Contacts will be updated from incoming messages.")
        else:
            print("[Bot] Syncing contacts from macOS Contacts app...")
            synced_count = sync_from_macos_contacts()
            if synced_count > 0:
                print(f"[Bot] SUCCESS: Loaded {synced_count} contacts from macOS Contacts app")
            else:
                print("[Bot] INFO: No contacts synced from macOS (will use contacts from iMessage)")
        except Exception as e:
            print(f"[Bot] WARNING: Could not sync macOS contacts: {e}")
            print("[Bot] INFO: Will use contacts from iMessage data instead")
    
    # Contacts are automatically loaded from JSON on module import
    from contact_manager import get_all_contacts
    contact_count = len(get_all_contacts())
    print(f"[Bot] SUCCESS: Contacts cache ready ({contact_count} contacts loaded)")
    
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
            
            # Track recently processed messages to avoid duplicates
            processed_messages = set()  # Store (chat_id, message_id, text_hash) tuples
            
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
                    
                    # Check for duplicate messages (prevent double processing)
                    import hashlib
                    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                    message_key = (str(chat_id), str(message_id), text_hash)
                    
                    if message_key in processed_messages:
                        print(f"[Bot] WARNING: Duplicate message detected (chat_id={chat_id}, message_id={message_id}), skipping...")
                        continue
                    
                    processed_messages.add(message_key)
                    # Keep only last 1000 processed messages to avoid memory issues
                    if len(processed_messages) > 1000:
                        # Remove oldest entries (simple FIFO - remove first 100)
                        processed_messages = set(list(processed_messages)[-900:])
                    
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
                                print(f"[Bot] Extracted contact from iPhone: {display_name} ({phone})")

                    # Skip empty messages (unless it's a location)
                    try:
                        is_location = is_location_message(data)
                    except Exception as e:
                        print(f"[Bot] WARNING: Error checking location: {e}")
                        is_location = False
                    
                    print(f"[Bot] Processing message: text='{text[:50] if text else 'EMPTY'}', is_location={is_location}, len={len(text) if text else 0}")
                    if not text and not is_location:
                        print(f"[Bot] Skipping empty message (no text and no location)")
                        continue
                    
                    print(f"[Bot] Message has content, continuing processing...")

                    # =========================
                    # LOCATION HANDLING (for address collection)
                    # =========================
                    # Check if this is a location message
                    if is_location:
                        print(f"[Bot] [LOCATION] Location message detected! Data keys: {list(data.keys())}")
                        print(f"[Bot] [LOCATION] Full data structure: {json.dumps(data, indent=2, default=str)[:500]}...")
                        
                        # Check if we're waiting for address in pending details
                        pending_detail = get_pending_details(str(chat_id))
                        if pending_detail:
                            # User shared location during order flow, convert to address
                            address = process_location_message(data, save_as_home=False)
                            if address:
                                print(f"[Bot] [LOCATION] Location received, converted to address: {address}")
                                # Use location as delivery address
                                pending_detail["delivery_address"] = address
                                pending_detail["location_received"] = True
                                
                                # If we already have user details, we can proceed
                                if pending_detail.get("user_details"):
                                    # We have both details and address, proceed to order
                                    set_pending_details(str(chat_id), pending_detail)
                                    # Fall through to process the order
                                else:
                                    # We have address but need order details
                                    set_pending_details(str(chat_id), pending_detail)
                                    reply_text = f"[LOCATION] Great! I got your location: {address}\n\nNow please provide:\n• What flavor/type would you like?\n• Size/quantity?\n• Any special instructions?"
                                    send_message(int(chat_id), reply_text)
                                    add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                    record_message_sent()
                                    record_response()
                                    continue
                            else:
                                reply_text = "[LOCATION] I received your location but couldn't convert it to an address. Please provide the address manually or try again."
                                send_message(int(chat_id), reply_text)
                                add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                record_message_sent()
                                record_response()
                                continue
                        else:
                            # Location shared but not in order flow - could be for saving home address
                            address = process_location_message(data, save_as_home=False)
                            if address:
                                print(f"[Bot] [LOCATION] Location received (not in order flow): {address}")
                                # Could prompt user if they want to save this as home address
                                # For now, just acknowledge
                                reply_text = f"[LOCATION] I received your location: {address}\n\nIf you're placing an order, please start with 'order pizza' and I'll use this location for delivery."
                                send_message(int(chat_id), reply_text)
                                add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                record_message_sent()
                                record_response()
                                continue
                            else:
                                print(f"[Bot] [WARNING] Location detected but couldn't extract coordinates")
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
                            reply_text = f"[OK] Great! I found '{contact_name}' in your contacts.\n\n Please provide order details:\n• What flavor/type would you like? (e.g., margherita, pepperoni)\n• Size/quantity?\n• Any special instructions?"
                        else:
                            reply_text = f"[OK] Great! I found '{contact_name}' in your contacts.\n\n Please provide details for your {action_type} request:"
                        
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
                    # Only process if permission was actually requested
                    from permission_manager import get_permission_status
                    permission_status = get_permission_status()
                    if permission_status["contacts"].get("requested", False):
                        permission_response = process_permission_response(text, str(chat_id), sender)
                        if permission_response:
                            if permission_response.get("granted"):
                                print(f"[Bot] [OK] Permission granted by user (silent)")
                                # Don't send message - just log it
                            else:
                                print(f"[Bot] [ERROR] Permission denied by user (silent)")
                                # Don't send message when denied - commented out
                                reply_text = permission_response.get("message", "")
                                if reply_text:  # Only send if message is not empty
                                    send_message(int(chat_id), reply_text)
                                    log_action("message_sent", {
                                        "chat_id": str(chat_id),
                                        "to": sender,
                                        "message": reply_text,
                                        "type": "permission_response"
                                    })
                                    add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                    record_message_sent()
                                    record_response()
                            # Only continue if we actually processed a permission response
                            continue
                        # If permission was requested but this isn't a permission response, continue normal processing
                    
                    # Check if there's pending details collection
                    # (re-check in case location was just processed above)
                    pending_detail = get_pending_details(str(chat_id))
                    if pending_detail:
                        # Check if location was received and use it as address
                        if pending_detail.get("location_received") and pending_detail.get("delivery_address"):
                            delivery_address = pending_detail.get("delivery_address")
                            print(f"[Bot] [LOCATION] Using location address: {delivery_address}")
                            # Clear location flag
                            pending_detail["location_received"] = False
                            # Continue to order processing with this address
                        # User provided details, now execute the action
                        from action_executor import execute_action
                        from user_preferences import extract_address_from_text, get_address_for_keyword, has_address
                        
                        action_type = pending_detail.get("action", "order")
                        contact_info = pending_detail.get("contact", {})
                        original_request = pending_detail.get("original_request", "")
                        
                        # Debug: Print contact info
                        print(f"[Bot]  Executing {action_type} action")
                        print(f"[Bot]  Contact info: {json.dumps(contact_info, indent=2)}")
                        print(f"[Bot]  Contact name: {contact_info.get('name')}")
                        print(f"[Bot]  Contact phone: {contact_info.get('phone_number')}")
                        print(f"[Bot]  Original request: {original_request}")
                        print(f"[Bot]  User details: {text}")
                        
                        # Verify contact has phone number
                        if not contact_info.get("phone_number") and not contact_info.get("phone"):
                            print(f"[Bot] [ERROR] Contact missing phone number!")
                            reply_text = f"[ERROR] Error: Contact '{contact_info.get('name', 'Unknown')}' doesn't have a phone number. Cannot send order."
                            send_message(int(chat_id), reply_text)
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            clear_pending_details(str(chat_id))
                            continue
                        
                        # Extract address information from user's details
                        delivery_address = None
                        text_lower = text.lower() if text else ""
                        
                        # First check if location was already received and processed
                        if pending_detail.get("delivery_address"):
                            delivery_address = pending_detail.get("delivery_address")
                            print(f"[Bot] [LOCATION] Using location address from shared location: {delivery_address}")
                        # Check if we're waiting for address (user already provided order details)
                        elif pending_detail.get("waiting_for_address"):
                            # User is providing address now
                            if "skip" not in text_lower:
                                delivery_address = text
                                pending_detail["waiting_for_address"] = False
                                
                                # If waiting for home address, save it
                                if pending_detail.get("waiting_for_home_address"):
                                    from user_preferences import set_home_address
                                    set_home_address(text)
                                    print(f"[Bot] 🏠 Saved home address: {text}")
                                    pending_detail["waiting_for_home_address"] = False
                        # Check if user mentioned "home" in their details
                        elif "home" in text_lower:
                            home_addr = get_address_for_keyword("home")
                            if home_addr:
                                delivery_address = home_addr
                                print(f"[Bot] 🏠 Using home address: {delivery_address}")
                            else:
                                # Home address not set, ask for it
                                reply_text = "🏠 I see you want delivery to 'home', but I don't have your home address saved yet.\n\nPlease provide your home address (I'll save it for future orders), or provide a different address."
                                send_message(int(chat_id), reply_text)
                                add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                # Update pending details to wait for address
                                pending_detail["waiting_for_address"] = True
                                pending_detail["waiting_for_home_address"] = True  # Flag to save it
                                pending_detail["user_details"] = text
                                set_pending_details(str(chat_id), pending_detail)
                                record_message_sent()
                                record_response()
                                continue
                        else:
                            # Try to extract address from text
                            extracted = extract_address_from_text(text)
                            if extracted and extracted not in ["home", "work"]:
                                delivery_address = extracted
                            # Check if address keywords are mentioned but no clear address
                            elif "address" in text_lower or "deliver" in text_lower or "delivery" in text_lower:
                                # User mentioned address but didn't provide it clearly - ask for it
                                reply_text = "[LOCATION] I need a delivery address. Please provide:\n• Full address (street, city, zip code)\n• Or say 'home' to use your saved home address\n• Or share your live location [LOCATION]"
                                send_message(int(chat_id), reply_text)
                                add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                pending_detail["waiting_for_address"] = True
                                pending_detail["user_details"] = text
                                set_pending_details(str(chat_id), pending_detail)
                                record_message_sent()
                                record_response()
                                continue
                        
                        # If no address found after processing details, ask for it
                        if not delivery_address and not pending_detail.get("waiting_for_address"):
                            # User provided order details but no address - ask for address
                            reply_text = "[LOCATION] Where should I deliver this order?\n\nPlease provide:\n• Full address (street, city, zip code)\n• Or say 'home' to use your saved home address\n• Or share your live location [LOCATION]"
                            send_message(int(chat_id), reply_text)
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            pending_detail["waiting_for_address"] = True
                            pending_detail["user_details"] = text
                            set_pending_details(str(chat_id), pending_detail)
                            record_message_sent()
                            record_response()
                            continue
                        
                        # Validate all required fields are filled before sending
                        details_text = pending_detail.get("user_details", text)
                        
                        # Check if address is required and provided
                        if not delivery_address:
                            # Address is missing - ask for it
                            reply_text = "[LOCATION] Where should I deliver this order?\n\nPlease provide:\n• Full address (street, city, zip code)\n• Or say 'home' to use your saved home address\n• Or share your live location [LOCATION]"
                            send_message(int(chat_id), reply_text)
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            pending_detail["waiting_for_address"] = True
                            pending_detail["user_details"] = text
                            set_pending_details(str(chat_id), pending_detail)
                            record_message_sent()
                            record_response()
                            continue
                        
                        # All fields are filled - prepare the request
                        # Extract order details from user_details
                        order_details = details_text if details_text else text
                        
                        # Build complete request with all information
                        full_request = f"Order: {order_details}. Delivery Address: {delivery_address}"
                        
                        # Execute the action
                        try:
                            result = execute_action(action_type, full_request, contact_info, str(chat_id), ai_client)
                            
                            print(f"[Bot]  Action result: {result}")
                            
                            if result.get("success"):
                                contact_name = contact_info.get("name") or contact_info.get("display_name", "Unknown")
                                sent_msg = result.get('sent_message', '')
                                
                                # Show full message with address
                                reply_text = f"[OK] Order sent to {contact_name}!\n\n Complete message sent:\n{sent_msg}"
                                print(f"[Bot] [OK] Order sent successfully to {contact_name}")
                                print(f"[Bot]  Full message with address: {sent_msg}")
                                
                                log_action("order_placed", {
                                    "chat_id": str(chat_id),
                                    "contact": contact_name,
                                    "contact_phone": contact_info.get("phone_number"),
                                    "item": full_request,
                                    "message_sent": sent_msg,
                                    "success": True
                                })
                            else:
                                error_msg = result.get('message', 'Unknown error')
                                error_detail = result.get('error', '')
                                reply_text = f"[ERROR] Failed to send order: {error_msg}"
                                if error_detail:
                                    reply_text += f"\n\nError: {error_detail}"
                                print(f"[Bot] [ERROR] Failed to send order: {error_msg}")
                                print(f"[Bot] [ERROR] Error details: {error_detail}")
                                
                                log_action("order_placed", {
                                    "chat_id": str(chat_id),
                                    "contact": contact_info.get("name", "Unknown"),
                                    "item": full_request,
                                    "success": False,
                                    "error": error_msg,
                                    "error_detail": error_detail
                                })
                            
                            clear_pending_details(str(chat_id))
                            
                            send_message(int(chat_id), reply_text)
                            log_action("message_sent", {
                                "chat_id": str(chat_id),
                                "to": sender,
                                "message": reply_text,
                                "type": "action_result"
                            })
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            record_message_sent()
                            record_response()
                            continue
                        except Exception as e:
                            import traceback
                            print(f"[Bot] [ERROR] Error executing action: {e}")
                            print(f"[Bot] [ERROR] Traceback: {traceback.format_exc()}")
                            
                            log_action("error", {
                                "chat_id": str(chat_id),
                                "error_type": "action_execution_error",
                                "action": action_type,
                                "error": str(e),
                                "traceback": traceback.format_exc()
                            })
                            
                            clear_pending_details(str(chat_id))
                            reply_text = f"[ERROR] Error sending order: {str(e)}. Please try again."
                            send_message(int(chat_id), reply_text)
                            log_action("message_sent", {
                                "chat_id": str(chat_id),
                                "to": sender,
                                "message": reply_text,
                                "type": "error_response"
                            })
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
                        print(f"[Bot] [BLOCKED] Message from {sender} blocked: {user_status.get('reason', 'unknown')}")
                        record_violation(sender, "blocked_user_attempt", {"chat_id": chat_id})
                        continue
                    
                    # Check rate limits
                    rate_ok, rate_reason = check_rate_limit(sender)
                    if not rate_ok:
                        print(f"[Bot] [BLOCKED] Rate limit exceeded for {sender}: {rate_reason}")
                        record_violation(sender, "rate_limit_exceeded", {"reason": rate_reason})
                        continue
                    
                    # Sanitize input
                    text = sanitize_input(text)
                    
                    # Check content safety
                    safety_check = check_content_safety(text, ai_client)
                    if not safety_check.get("safe", True):
                        print(f"[Bot] [BLOCKED] Unsafe content from {sender}: {safety_check.get('message', 'unknown')}")
                        record_violation(sender, safety_check.get("reason", "unsafe_content"), safety_check)
                        flag_user(sender, safety_check.get("reason", "unsafe_content"), safety_check.get("severity", "medium"))
                        continue
                    
                    # Record message for rate limiting
                    record_message(sender)
                    print(f"[Bot]  Message recorded for rate limiting")

                    # Get contact information
                    contact = get_contact_by_phone(sender)
                    contact_name = contact.get("name") or contact.get("display_name") if contact else sender
                    
                    print(f"[Bot]  New message in chat {chat_id} from {contact_name} ({sender}): {text}")
                    print(f"[Bot] 🔄 Starting message processing pipeline...")

                    # Track message in conversation thread
                    add_message(str(chat_id), sender, text, message_id, is_bot=False)
                    
                    # Check if this is a reply to a tracked message (for follow-up cancellation)
                    is_follow_up_reply = check_for_reply(str(chat_id), sender)
                    if is_follow_up_reply:
                        print(f"[Bot] [OK] Reply received - follow-up canceled")
                    
                    # Check if this is a reply
                    has_replied_recently = has_replied(str(chat_id), sender, within_minutes=60)
                    if has_replied_recently:
                        print(f"[Bot]  User {contact_name} has replied within the last hour")

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
                            print(f"[Bot] [WARNING] Rate limit check: {limit_reason}")
                            print(f"[Bot] Message received and processed, but reply blocked by rate limit.")
                            # Still update analytics for received message
                            continue
                        
                        # =========================
                        # CHECK FOR MEMORY RETRIEVAL REQUESTS
                        # =========================
                        text_lower = text.lower().strip()
                        if is_memory_retrieval_request(text):
                            print(f"[Bot] 🧠 Detected memory retrieval request")
                            try:
                                memory_response = process_memory_request(text, str(chat_id))
                                if memory_response:
                                    reply_text = memory_response
                                    send_message(int(chat_id), reply_text)
                                    log_action("message_sent", {
                                        "chat_id": str(chat_id),
                                        "to": sender,
                                        "message": reply_text,
                                        "type": "memory_retrieval"
                                    })
                                    add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                    record_message_sent()
                                    record_response()
                                    continue
                            except Exception as e:
                                print(f"[Bot] [WARNING] Memory retrieval error: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # =========================
                        # CHECK FOR MEETING/EMAIL QUERIES (Non-blocking)
                        # =========================
                        meeting_keywords = ["meeting", "meetings", "appointment", "appointments", "calendar", "schedule"]
                        email_keywords = ["urgent", "email", "emails", "mail", "mails", "inbox"]
                        is_meeting_query = any(keyword in text_lower for keyword in meeting_keywords)
                        is_email_query = any(keyword in text_lower for keyword in email_keywords)
                        
                        if is_meeting_query or is_email_query:
                            print(f"[Bot]  Detected meeting/email query, checking Gmail/Calendar...")
                            import threading
                            def check_meetings_async():
                                try:
                                    summary = get_meetings_and_emails_summary()
                                    send_message(int(chat_id), summary)
                                    log_action("message_sent", {
                                        "chat_id": str(chat_id),
                                        "to": sender,
                                        "message": summary,
                                        "type": "meeting_email_summary"
                                    })
                                    from messaging_rules import should_separate_from_conversation
                                    if not should_separate_from_conversation(summary):
                                        add_message(str(chat_id), sender, summary, None, is_bot=True)
                                    record_message_sent()
                                    record_response()
                                except Exception as e:
                                    print(f"[Bot] [ERROR] Error checking meetings/emails: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    error_msg = "[ERROR] Error checking meetings/emails. Please try again later."
                                    send_message(int(chat_id), error_msg)
                                    from messaging_rules import should_separate_from_conversation
                                    if not should_separate_from_conversation(error_msg):
                                        add_message(str(chat_id), sender, error_msg, None, is_bot=True)
                            
                            thread = threading.Thread(target=check_meetings_async, daemon=True)
                            thread.start()
                            status_msg = " Checking your meetings and emails... I'll send the results shortly."
                            send_message(int(chat_id), status_msg)
                            from messaging_rules import should_separate_from_conversation
                            if not should_separate_from_conversation(status_msg):
                                add_message(str(chat_id), sender, status_msg, None, is_bot=True)
                            record_message_sent()
                            record_response()
                            continue
                        
                        # =========================
                        # MULTI-AGENT SYSTEM: Check if request needs contact-based action
                        # ONLY for Order, Call, and Send actions with specific keywords
                        # =========================
                        # Initialize agent_result to track if actionable request was processed
                        agent_result = None
                        is_actionable = False
                        
                        # Define allowed keywords for contact management actions
                        ORDER_KEYWORDS = ["order", "buy", "purchase", "get me"]
                        CALL_KEYWORDS = ["call", "phone", "ring", "dial"]
                        SEND_KEYWORDS = ["send", "message", "text", "text message", "send message"]
                        
                        # Query keywords that should NOT trigger contact actions (but allow "can you order" type requests)
                        query_keywords = ["see", "show", "view", "check", "what", "when", "where", "how", "why", "tell", "list", "display", "alert", "alerts", "reminder", "reminders", "meeting", "meetings", "email", "emails"]
                        
                        # Check if message contains allowed action keywords
                        has_order_keyword = any(keyword in text_lower for keyword in ORDER_KEYWORDS)
                        has_call_keyword = any(keyword in text_lower for keyword in CALL_KEYWORDS)
                        has_send_keyword = any(keyword in text_lower for keyword in SEND_KEYWORDS)
                        
                        # Check for query keywords that should NOT trigger contact actions
                        # But allow action keywords even if query words are present (e.g., "can you order pizza" should work)
                        has_query_keyword = any(keyword in text_lower for keyword in query_keywords)
                        
                        # Only trigger if it's an allowed action
                        # Priority: If action keyword exists, trigger regardless of query words (e.g., "can you order pizza")
                        is_actionable = has_order_keyword or has_call_keyword or has_send_keyword
                        
                        # But exclude pure queries without action intent (e.g., "what is order" without wanting to order)
                        if is_actionable and has_query_keyword:
                            # If it's a pure query about the action (not requesting the action), skip
                            # Examples: "what is order", "how to order" (without wanting to actually order)
                            # But allow: "can you order", "please order", "I need to order"
                            pure_query_patterns = ["what is", "how to", "explain", "define", "what does"]
                            is_pure_query = any(pattern in text_lower for pattern in pure_query_patterns)
                            if is_pure_query and not any(word in text_lower for word in ["for me", "me", "my", "please", "can you", "could you", "would you"]):
                                is_actionable = False
                                print(f"[Bot]  Detected pure query about action, not actionable request")
                        
                        if is_actionable:
                            print(f"[Bot]  Detected actionable request, processing with multi-agent system...")
                            try:
                                agent_result = process_user_request(text, str(chat_id), sender, ai_client)
                                
                                # COMMENTED OUT: Skip permission check - process regardless
                                # if agent_result.get("needs_permission"):
                                #     # Permission required
                                #     reply_text = agent_result.get("message", "Permission required to access contacts")
                                #     print(f"[Bot] 🔐 Permission required for contact access")
                                if agent_result and agent_result.get("success"):
                                    # Action executed successfully
                                    reply_text = f"[OK] {agent_result.get('message', 'Action completed')}"
                                    if agent_result.get("sent_message"):
                                        reply_text += f"\n\nSent: {agent_result.get('sent_message', '')[:100]}..."
                                    print(f"[Bot] [OK] Agent action successful: {agent_result.get('action')} with {agent_result.get('contact')}")
                                    
                                    send_message(int(chat_id), reply_text)
                                    log_action("message_sent", {
                                        "chat_id": str(chat_id),
                                        "to": sender,
                                        "message": reply_text,
                                        "type": "agent_response",
                                        "agent_action": agent_result.get("action", "unknown")
                                    })
                                    add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                    record_message_sent()
                                    record_response()
                                    continue
                                elif agent_result and agent_result.get("needs_confirmation"):
                                    # Action needs confirmation
                                    contact_info = agent_result.get("contact", {})
                                    contact_name = contact_info.get("name") or contact_info.get("display_name", "Unknown")
                                    action_type = agent_result.get("action", "order")
                                    
                                    # Set pending confirmation
                                    set_pending_confirmation(str(chat_id), {
                                        "action": action_type,
                                        "contact": contact_info,
                                        "original_request": text
                                    })
                                    
                                    reply_text = f"[OK] I found '{contact_name}' in your contacts. Should I proceed with {action_type}? (Reply 'yes' to continue)"
                                    print(f"[Bot] [WARNING] Agent action needs confirmation: {agent_result.get('message')}")
                                    
                                    send_message(int(chat_id), reply_text)
                                    log_action("message_sent", {
                                        "chat_id": str(chat_id),
                                        "to": sender,
                                        "message": reply_text,
                                        "type": "agent_response",
                                        "agent_action": agent_result.get("action", "unknown")
                                    })
                                    add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                                    record_message_sent()
                                    record_response()
                                    continue
                                else:
                                    # Action failed or no contact found - fall through to normal response
                                    print(f"[Bot] [WARNING] Agent action failed or no contact found, using normal AI response")
                                    agent_result = None  # Reset to allow normal response
                                
                            except Exception as e:
                                print(f"[Bot] [WARNING] Agent system error: {e}, falling back to normal response")
                                import traceback
                                traceback.print_exc()
                                agent_result = None  # Reset on error to allow normal response
                        
                        # Generate AI response with context (normal flow)
                        # Only skip if actionable request was successfully processed AND a response was already sent
                        should_skip_response = False
                        if is_actionable and agent_result:
                            # Only skip if action was successful OR needs confirmation (both cases send a response)
                            if agent_result.get("success") or agent_result.get("needs_confirmation"):
                                should_skip_response = True
                                print(f"[Bot]   Skipping normal AI response - actionable request already handled")
                        
                        if not should_skip_response:
                            print(f"[Bot]  Generating normal AI response...")
                            reply_text = generate_response(text, str(chat_id), sender, analysis, ai_client)
                            
                            # =========================
                            # GUARDRAILS: Response Validation
                            # =========================
                            response_validation = validate_response(reply_text, ai_client)
                            if not response_validation.get("valid", True):
                                print(f"[Bot] [BLOCKED] Response validation failed: {response_validation.get('message', 'unknown')}")
                                # Generate a safe fallback response
                                reply_text = "I apologize, but I'm unable to provide a response to that. How else can I help you?"
                            
                            # Track bot message in conversation thread
                            # Only send ONE response per message
                            send_message(int(chat_id), reply_text)
                            add_message(str(chat_id), sender, reply_text, None, is_bot=True)
                            
                            record_message_sent()  # Track for rate limiting
                            record_response()
                            print(f"[Bot] [OK] Sent AI reply: {reply_text}")
                        
                        # Mark this message as fully processed to prevent duplicate responses
                        processed_messages.add(message_key)
                        
                        # Log conversation summary
                        summary = get_conversation_summary(str(chat_id))
                        print(f"[Bot]  Conversation summary: {summary['message_count']} messages, {len(summary['participants'])} participants")
                        
                        # Special handling for summary requests
                        if "summary" in text.lower() or "summarize" in text.lower():
                            summary = generate_summary(str(chat_id), ai_client)
                            send_message(int(chat_id), f"📋 Conversation Summary: {summary}")
                            print(f"[Bot] [OK] Sent summary for chat {chat_id}")
                        
                        # Print analytics every 5 messages
                        if message_count % 5 == 0:
                            print_analytics()
                            
                    except Exception as e:
                        error_msg = str(e)
                        if "Rate limit" in error_msg or "429" in error_msg:
                            print(f"[Bot] [WARNING] RATE LIMIT HIT! Message received but cannot reply.")
                            print(f"[Bot] This might be due to organizer-set limits. Message was still processed.")
                        elif "Quota" in error_msg or "403" in error_msg:
                            print(f"[Bot] [WARNING] QUOTA EXCEEDED! Message received but cannot reply.")
                            print(f"[Bot] Check if you've hit the message limit set by organizers.")
                        else:
                            print(f"[Bot] [ERROR] Failed to send reply: {e}")
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

