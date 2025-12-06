"""Execute actions based on user requests and matched contacts."""
import json
from typing import Dict, Optional, List
from openai import OpenAI
from series_api import send_message, create_chat
from contact_manager import get_contact_name
from conversation_tracker import get_conversation_thread
from email_client import send_email_to_contact
from action_history import log_action
from messaging_rules import get_allowed_recipient, validate_recipient

def execute_action(
    action_type: str,
    request: str,
    contact: Dict,
    chat_id: str,
    ai_client: Optional[OpenAI] = None
) -> Dict:
    """Execute an action using a matched contact.
    Only supports: order, call, message (send) actions."""
    
    # Only allow specific action types
    ALLOWED_ACTIONS = ["order", "call", "message"]
    
    if action_type not in ALLOWED_ACTIONS:
        return {
            "action": action_type,
            "success": False,
            "message": f"Action '{action_type}' is not supported. Only 'order', 'call', and 'send' (message) are allowed.",
            "error": "Unsupported action type",
            "allowed_actions": ALLOWED_ACTIONS
        }
    
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    # Try multiple possible phone number fields
    contact_phone = (
        contact.get("phone_number") or 
        contact.get("phone") or 
        contact.get("identifier", "")
    )
    
    # Debug logging
    print(f"[ActionExecutor] Executing {action_type} action")
    print(f"[ActionExecutor] Contact: {contact_name}")
    print(f"[ActionExecutor] Phone: {contact_phone}")
    print(f"[ActionExecutor] Full contact dict: {contact}")
    
    result = {
        "action": action_type,
        "contact": contact_name,
        "phone": contact_phone,
        "success": False,
        "message": "",
        "error": None
    }
    
    try:
        if action_type == "order":
            result = _execute_order(request, contact, chat_id, ai_client)
        elif action_type == "call":
            result = _execute_call(request, contact, chat_id, ai_client)
        elif action_type == "message":
            result = _execute_message(request, contact, chat_id, ai_client)
        else:
            # Should not reach here due to check above, but fallback to message
            result = _execute_message(request, contact, chat_id, ai_client)
        
        result["contact"] = contact_name
        result["phone"] = contact_phone
        
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
        result["message"] = f"Failed to execute action: {e}"
    
    return result

def _execute_order(request: str, contact: Dict, chat_id: str, ai_client: Optional[OpenAI]) -> Dict:
    """Execute an order action (e.g., order pizza). Uses contact from cache."""
    # Get contact from cache to ensure we have latest info
    from contact_manager import get_contact_by_phone, get_all_contacts
    
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    contact_phone = (
        contact.get("phone_number") or 
        contact.get("phone") or 
        contact.get("identifier", "")
    )
    
    # Try to get contact from cache by name (e.g., "Pizza Guy")
    cached_contacts = get_all_contacts()
    cached_contact = None
    for c in cached_contacts:
        if (c.get("name") == contact_name or 
            c.get("display_name") == contact_name or
            c.get("phone_number") == contact_phone):
            cached_contact = c
            break
    
    # Use cached contact if found, otherwise use provided contact
    if cached_contact:
        contact = cached_contact
        contact_name = contact.get("name") or contact.get("display_name", "Unknown")
        contact_phone = contact.get("phone_number") or contact_phone
        print(f"[ActionExecutor] [OK] Using contact from cache: {contact_name}")
    
    print(f"[ActionExecutor] _execute_order called")
    print(f"[ActionExecutor] Contact name: {contact_name}")
    print(f"[ActionExecutor] Contact phone: {contact_phone}")
    print(f"[ActionExecutor] Full contact: {contact}")
    
    # Extract order details and address from request - NO AI, NO FILLER
    # Request format: "Order: [details]. Delivery Address: [address]"
    order_parts = request.split("Delivery Address:")
    order_details = order_parts[0].replace("Order:", "").strip() if len(order_parts) > 0 else request
    delivery_address = order_parts[1].strip() if len(order_parts) > 1 else None
    
    # Validate all required fields are present before sending
    if not order_details or order_details == "":
        return {
            "action": "order",
            "success": False,
            "message": "Order details are missing. Cannot send order.",
            "error": "Missing order details"
        }
    
    if not delivery_address or delivery_address == "":
        return {
            "action": "order",
            "success": False,
            "message": "Delivery address is missing. Cannot send order.",
            "error": "Missing delivery address"
        }
    
    # Build message directly from provided information - NO FILLER TEXT
    message_text = f"Hi, I'd like to place an order.\n\n"
    message_text += f"Order Details: {order_details}\n\n"
    message_text += f"Delivery Address: {delivery_address}\n\n"
    message_text += "Please confirm if this works. Thank you!"
    
    # Create chat and send message
    # Validate phone number
    if not contact_phone:
        return {
            "action": "order",
            "success": False,
            "message": f"No phone number found for {contact_name}",
            "error": "Missing phone number"
        }
    
    # Ensure phone number is in correct format
    # Remove "missing value" if present
    phone_clean = contact_phone.replace("missing value", "").strip()
    
    # Extract only digits
    digits_only = ''.join(filter(str.isdigit, phone_clean))
    
    if not digits_only:
        return {
            "action": "order",
            "success": False,
            "message": f"No valid phone number found for {contact_name}",
            "error": "Invalid phone number - no digits found"
        }
    
    # Format phone number: must be in E.164 format (+1XXXXXXXXXX)
    if len(digits_only) == 10:
        # 10 digits: add +1 country code
        phone_clean = f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith("1"):
        # 11 digits starting with 1: add +
        phone_clean = f"+{digits_only}"
    elif digits_only.startswith("+") or phone_clean.startswith("+"):
        # Already has +, just ensure it's clean
        phone_clean = "+" + ''.join(filter(str.isdigit, phone_clean.replace("+", "")))
        if len(phone_clean.replace("+", "")) == 10:
            phone_clean = f"+1{phone_clean.replace('+', '')}"
        elif len(phone_clean.replace("+", "")) == 11 and phone_clean.replace("+", "").startswith("1"):
            phone_clean = "+" + phone_clean.replace("+", "")
    else:
        return {
            "action": "order",
            "success": False,
            "message": f"Invalid phone number format for {contact_name}: {contact_phone} (got {len(digits_only)} digits)",
            "error": f"Phone number format invalid: {contact_phone} - expected 10 or 11 digits"
        }
    
    print(f"[ActionExecutor] 📞 Original phone: {contact_phone}")
    print(f"[ActionExecutor] 📞 Cleaned phone: {phone_clean}")
    
    print(f"[ActionExecutor] 📞 Sending order to {contact_name}")
    print(f"[ActionExecutor] 📞 Phone number: {phone_clean}")
    print(f"[ActionExecutor]  Order message: {message_text[:150]}...")
    print(f"[ActionExecutor]  Full message: {message_text}")
    
    # Create new chat with the contact's phone number
    # This will create a chat between the bot (sender) and the contact
    print(f"[ActionExecutor] ========================================")
    print(f"[ActionExecutor] 📤 SENDING ORDER MESSAGE")
    print(f"[ActionExecutor] ========================================")
    print(f"[ActionExecutor] Contact Name: {contact_name}")
    print(f"[ActionExecutor] Phone Number: {phone_clean}")
    print(f"[ActionExecutor] Message: {message_text}")
    print(f"[ActionExecutor] ========================================")
    
    try:
        # Send to actual contact phone number, not just allowed recipient
        recipient_phone = phone_clean  # Use the cleaned contact phone number
        
        print(f"[ActionExecutor] 📤 Sending order to contact: {contact_name} at {recipient_phone}")
        
        response = create_chat(
            phone_numbers=[recipient_phone],
            message_text=message_text,
            display_name=contact_name,
            enforce_recipient=False  # Don't enforce - use actual contact number
        )
        
        print(f"[ActionExecutor] [OK] API Response received")
        print(f"[ActionExecutor] [OK] Response data: {json.dumps(response, indent=2)}")
        
        new_chat_id = response.get("chat_id") or response.get("data", {}).get("chat_id")
        if not new_chat_id:
            print(f"[ActionExecutor] [WARNING] Warning: No chat_id in response. Response: {json.dumps(response, indent=2)}")
        
        print(f"[ActionExecutor] [OK] Order sent successfully! Chat ID: {new_chat_id}")
        
        # Log action for dashboard
        log_action("order", {
            "chat_id": str(new_chat_id) if new_chat_id else str(chat_id),
            "contact": contact_name,
            "contact_phone": phone_clean,
            "order_details": order_details,
            "delivery_address": delivery_address,
            "message_sent": message_text,
            "success": True
        })
        
        # Track order event in contact metadata
        try:
            from contact_manager import update_contact_info
            from datetime import datetime
            
            # Get event_id from response if available
            event_id = response.get("event_id") or response.get("data", {}).get("event_id", "")
            
            # Update contact with order history
            current_metadata = contact.get("metadata", {})
            if "recent_orders" not in current_metadata:
                current_metadata["recent_orders"] = []
            
            # Add new order to history (keep last 10 orders)
            order_entry = {
                "event_id": event_id,
                "order_message": message_text[:200],  # Store first 200 chars
                "timestamp": datetime.now().isoformat(),
                "chat_id": str(new_chat_id) if new_chat_id else ""
            }
            current_metadata["recent_orders"].insert(0, order_entry)
            current_metadata["recent_orders"] = current_metadata["recent_orders"][:10]  # Keep last 10
            
            # Update contact
            update_contact_info(contact_phone, {
                "metadata": current_metadata,
                "last_order": datetime.now().isoformat()
            })
            print(f"[ActionExecutor]  Order event tracked in contact metadata")
        except Exception as e:
            print(f"[ActionExecutor] [WARNING] Error tracking order in metadata: {e}")
        
        return {
            "action": "order",
            "success": True,
            "message": f"Order message sent to {contact_name}",
            "chat_id": new_chat_id or response.get("chat_id"),
            "sent_message": message_text,
            "event_id": event_id
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ActionExecutor] [ERROR] Error sending order: {e}")
        print(f"[ActionExecutor] Error details: {error_details}")
        return {
            "action": "order",
            "success": False,
            "message": f"Failed to send order to {contact_name}: {str(e)}",
            "error": str(e)
        }

def _execute_call(request: str, contact: Dict, chat_id: str, ai_client: Optional[OpenAI]) -> Dict:
    """Execute a call action (inform user to call)."""
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    contact_phone = contact.get("phone_number", "")
    
    # Log action for dashboard
    log_action("call", {
        "chat_id": str(chat_id),
        "contact": contact_name,
        "contact_phone": contact_phone,
        "request": request,
        "success": True
    })
    
    return {
        "action": "call",
        "success": True,
        "message": f"Please call {contact_name} at {contact_phone}",
        "instruction": f"Call {contact_name} at {contact_phone} regarding: {request}"
    }

def _execute_email(request: str, contact: Dict, chat_id: str, ai_client: Optional[OpenAI]) -> Dict:
    """Execute an email action - send email to contact."""
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    contact_email = contact.get("email") or contact.get("email_address", "")
    
    if not contact_email:
        return {
            "action": "email",
            "success": False,
            "message": f"No email address found for {contact_name}",
            "error": "Missing email address"
        }
    
    # Generate email subject and body using conversation history as few-shot examples
    subject = f"Re: {request[:50]}"
    body = f"Hello,\n\n{request}\n\nBest regards"
    
    if ai_client:
        try:
            thread = get_conversation_thread(chat_id, limit=20)
            
            # Build few-shot examples from conversation history
            examples = []
            for msg in thread[-10:]:  # Last 10 messages as examples
                role = "assistant" if msg.get("is_bot") else "user"
                text = msg.get("text", "")
                if text:
                    examples.append(f"{'Bot' if role == 'assistant' else 'User'}: {text}")
            
            context_examples = "\n".join(examples) if examples else "No previous conversation"
            
            email_content = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Generate a professional email for {contact_name}. 
Use the conversation history below as few-shot examples to understand:
- The user's communication style and preferences
- Previous context and details mentioned
- How to structure the email naturally

Generate an email that:
1. Has a clear, concise subject line
2. Is professional but matches the conversation tone
3. Includes ALL details from the user's request
4. References relevant context from the conversation if needed
5. Is clear and complete

Return your response in this format:
SUBJECT: [subject line]
BODY: [email body]"""
                    },
                    {
                        "role": "system",
                        "content": f"Conversation history (few-shot examples):\n{context_examples}"
                    },
                    {
                        "role": "user",
                        "content": f"User's email request: {request}\n\nGenerate the email to send to {contact_name}:"
                    }
                ],
                temperature=0.7,
                max_tokens=400
            )
            email_text = email_content.choices[0].message.content.strip()
            
            # Parse subject and body
            if "SUBJECT:" in email_text and "BODY:" in email_text:
                parts = email_text.split("BODY:")
                subject = parts[0].replace("SUBJECT:", "").strip()
                body = parts[1].strip() if len(parts) > 1 else body
            elif "Subject:" in email_text:
                parts = email_text.split("Subject:")
                if len(parts) > 1:
                    body_parts = parts[1].split("\n", 1)
                    subject = body_parts[0].strip()
                    body = body_parts[1].strip() if len(body_parts) > 1 else body
            else:
                # If format not recognized, use first line as subject, rest as body
                lines = email_text.split("\n")
                if len(lines) > 1:
                    subject = lines[0].strip()
                    body = "\n".join(lines[1:]).strip()
                else:
                    body = email_text
        except Exception as e:
            print(f"[ActionExecutor] Error generating email content: {e}")
            subject = f"Re: {request[:50]}"
            body = f"Hello,\n\n{request}\n\nBest regards"
    
    # Send email
    print(f"[ActionExecutor] 📧 Sending email to {contact_name} ({contact_email})")
    print(f"[ActionExecutor] 📧 Subject: {subject}")
    print(f"[ActionExecutor] 📧 Body: {body[:100]}...")
    
    result = send_email_to_contact(contact, subject, body)
    
    if result.get("success"):
        return {
            "action": "email",
            "success": True,
            "message": f"Email sent to {contact_name}",
            "to": contact_email,
            "subject": subject,
            "sent_message": body
        }
    else:
        return {
            "action": "email",
            "success": False,
            "message": f"Failed to send email to {contact_name}: {result.get('error', 'Unknown error')}",
            "error": result.get("error", "Unknown error")
        }

def _execute_message(request: str, contact: Dict, chat_id: str, ai_client: Optional[OpenAI]) -> Dict:
    """Execute a message action."""
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    contact_phone = contact.get("phone_number", "")
    
    # Generate message using conversation history as few-shot examples
    if ai_client:
        try:
            thread = get_conversation_thread(chat_id, limit=20)
            
            # Build few-shot examples from conversation history
            examples = []
            for msg in thread[-10:]:  # Last 10 messages as examples
                role = "assistant" if msg.get("is_bot") else "user"
                text = msg.get("text", "")
                if text:
                    examples.append(f"{'Bot' if role == 'assistant' else 'User'}: {text}")
            
            context_examples = "\n".join(examples) if examples else "No previous conversation"
            
            message = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Generate a professional message for {contact_name}. 
Use the conversation history below as few-shot examples to understand:
- The user's communication style
- Previous context and details
- How to structure the message naturally"""
                    },
                    {
                        "role": "system",
                        "content": f"Conversation history (few-shot examples):\n{context_examples}"
                    },
                    {
                        "role": "user",
                        "content": f"User's request: {request}\n\nGenerate the message to send to {contact_name}:"
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            message_text = message.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ActionExecutor] Error generating message: {e}")
            message_text = f"Hello, {request}"
    else:
        message_text = f"Hello, {request}"
    
    try:
        # Send to actual contact phone number
        recipient_phone = contact_phone
        if not recipient_phone.startswith("+"):
            if recipient_phone.startswith("1") and len(recipient_phone) == 11:
                recipient_phone = f"+{recipient_phone}"
            elif len(recipient_phone) == 10:
                recipient_phone = f"+1{recipient_phone}"
        
        print(f"[ActionExecutor] 📤 Sending message to contact: {contact_name} at {recipient_phone}")
        
        response = create_chat(
            phone_numbers=[recipient_phone],
            message_text=message_text,
            display_name=contact_name,
            enforce_recipient=False  # Don't enforce - use actual contact number
        )
        
        chat_id_from_response = response.get("chat_id") or response.get("data", {}).get("chat_id")
        if not chat_id_from_response:
            print(f"[ActionExecutor] [WARNING] Warning: No chat_id in response. Response: {json.dumps(response, indent=2)}")
        
        # Track this message for follow-up scheduling
        # Use the new chat_id where message was sent, or fallback to original chat_id
        follow_up_chat_id = str(chat_id_from_response) if chat_id_from_response else chat_id
        
        # Log action for dashboard
        log_action("message", {
            "chat_id": str(follow_up_chat_id),
            "contact": contact_name,
            "contact_phone": recipient_phone,
            "message_sent": message_text,
            "success": True
        })
        
        try:
            from follow_up_scheduler import track_sent_message
            track_sent_message(
                chat_id=follow_up_chat_id,
                recipient_phone=contact_phone,
                recipient_name=contact_name,
                message_text=message_text,
                original_chat_id=str(chat_id)
            )
            print(f"[ActionExecutor]  Message tracked for follow-up scheduling")
        except Exception as e:
            print(f"[ActionExecutor] [WARNING] Error tracking message for follow-up: {e}")
            # Don't fail the action if tracking fails
        
        return {
            "action": "message",
            "success": True,
            "message": f"Message sent to {contact_name}",
            "chat_id": chat_id_from_response or response.get("chat_id"),
            "sent_message": message_text
        }
    except Exception as e:
        return {
            "action": "message",
            "success": False,
            "message": f"Failed to message {contact_name}",
            "error": str(e)
        }

def _execute_book(request: str, contact: Dict, chat_id: str, ai_client: Optional[OpenAI]) -> Dict:
    """Execute a booking action."""
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    contact_phone = contact.get("phone_number", "")
    
    # Generate booking message using conversation history as few-shot examples
    if ai_client:
        try:
            thread = get_conversation_thread(chat_id, limit=20)
            
            # Build few-shot examples from conversation history
            examples = []
            for msg in thread[-10:]:
                role = "assistant" if msg.get("is_bot") else "user"
                text = msg.get("text", "")
                if text:
                    examples.append(f"{'Bot' if role == 'assistant' else 'User'}: {text}")
            
            context_examples = "\n".join(examples) if examples else "No previous conversation"
            
            booking_message = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Generate a professional booking request message for {contact_name}.
Use the conversation history below as few-shot examples to understand context and style."""
                    },
                    {
                        "role": "system",
                        "content": f"Conversation history (few-shot examples):\n{context_examples}"
                    },
                    {
                        "role": "user",
                        "content": f"User wants to book: {request}\n\nGenerate the booking message:"
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            message_text = booking_message.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ActionExecutor] Error generating booking message: {e}")
            message_text = f"Hello, I would like to make a booking. {request}"
    else:
        message_text = f"Hello, I would like to make a booking. {request}"
    
    try:
        # Send to actual contact phone number
        recipient_phone = contact_phone
        if not recipient_phone.startswith("+"):
            if recipient_phone.startswith("1") and len(recipient_phone) == 11:
                recipient_phone = f"+{recipient_phone}"
            elif len(recipient_phone) == 10:
                recipient_phone = f"+1{recipient_phone}"
        
        print(f"[ActionExecutor] 📤 Sending booking to contact: {contact_name} at {recipient_phone}")
        
        response = create_chat(
            phone_numbers=[recipient_phone],
            message_text=message_text,
            display_name=contact_name,
            enforce_recipient=False  # Don't enforce - use actual contact number
        )
        
        chat_id_from_response = response.get("chat_id") or response.get("data", {}).get("chat_id")
        if not chat_id_from_response:
            print(f"[ActionExecutor] [WARNING] Warning: No chat_id in response. Response: {json.dumps(response, indent=2)}")
        
        return {
            "action": "book",
            "success": True,
            "message": f"Booking request sent to {contact_name}",
            "chat_id": chat_id_from_response or response.get("chat_id"),
            "sent_message": message_text
        }
    except Exception as e:
        return {
            "action": "book",
            "success": False,
            "message": f"Failed to send booking to {contact_name}",
            "error": str(e)
        }

def _execute_schedule(request: str, contact: Dict, chat_id: str, ai_client: Optional[OpenAI]) -> Dict:
    """Execute a scheduling action."""
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    contact_phone = contact.get("phone_number", "")
    
    # Generate scheduling message using conversation history as few-shot examples
    if ai_client:
        try:
            thread = get_conversation_thread(chat_id, limit=20)
            
            # Build few-shot examples from conversation history
            examples = []
            for msg in thread[-10:]:
                role = "assistant" if msg.get("is_bot") else "user"
                text = msg.get("text", "")
                if text:
                    examples.append(f"{'Bot' if role == 'assistant' else 'User'}: {text}")
            
            context_examples = "\n".join(examples) if examples else "No previous conversation"
            
            schedule_message = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Generate a professional scheduling request message for {contact_name}.
Use the conversation history below as few-shot examples to understand context and style."""
                    },
                    {
                        "role": "system",
                        "content": f"Conversation history (few-shot examples):\n{context_examples}"
                    },
                    {
                        "role": "user",
                        "content": f"User wants to schedule: {request}\n\nGenerate the scheduling message:"
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            message_text = schedule_message.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ActionExecutor] Error generating scheduling message: {e}")
            message_text = f"Hello, I would like to schedule an appointment. {request}"
    else:
        message_text = f"Hello, I would like to schedule an appointment. {request}"
    
    try:
        # Send to actual contact phone number
        recipient_phone = contact_phone
        if not recipient_phone.startswith("+"):
            if recipient_phone.startswith("1") and len(recipient_phone) == 11:
                recipient_phone = f"+{recipient_phone}"
            elif len(recipient_phone) == 10:
                recipient_phone = f"+1{recipient_phone}"
        
        print(f"[ActionExecutor] 📤 Sending schedule request to contact: {contact_name} at {recipient_phone}")
        
        response = create_chat(
            phone_numbers=[recipient_phone],
            message_text=message_text,
            display_name=contact_name,
            enforce_recipient=False  # Don't enforce - use actual contact number
        )
        
        chat_id_from_response = response.get("chat_id") or response.get("data", {}).get("chat_id")
        if not chat_id_from_response:
            print(f"[ActionExecutor] [WARNING] Warning: No chat_id in response. Response: {json.dumps(response, indent=2)}")
        
        return {
            "action": "schedule",
            "success": True,
            "message": f"Scheduling request sent to {contact_name}",
            "chat_id": chat_id_from_response or response.get("chat_id"),
            "sent_message": message_text
        }
    except Exception as e:
        return {
            "action": "schedule",
            "success": False,
            "message": f"Failed to send scheduling request to {contact_name}",
            "error": str(e)
        }

