"""Execute actions based on user requests and matched contacts."""
from typing import Dict, Optional, List
from openai import OpenAI
from series_api import send_message, create_chat
from contact_manager import get_contact_name
from conversation_tracker import get_conversation_thread
from email_client import send_email_to_contact

def execute_action(
    action_type: str,
    request: str,
    contact: Dict,
    chat_id: str,
    ai_client: Optional[OpenAI] = None
) -> Dict:
    """Execute an action using a matched contact."""
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
        elif action_type == "email":
            result = _execute_email(request, contact, chat_id, ai_client)
        elif action_type == "book":
            result = _execute_book(request, contact, chat_id, ai_client)
        elif action_type == "schedule":
            result = _execute_schedule(request, contact, chat_id, ai_client)
        else:
            # Default: send a message
            result = _execute_message(request, contact, chat_id, ai_client)
        
        result["contact"] = contact_name
        result["phone"] = contact_phone
        
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
        result["message"] = f"Failed to execute action: {e}"
    
    return result

def _execute_order(request: str, contact: Dict, chat_id: str, ai_client: Optional[OpenAI]) -> Dict:
    """Execute an order action (e.g., order pizza)."""
    contact_name = contact.get("name") or contact.get("display_name", "Unknown")
    # Try multiple possible phone number fields
    contact_phone = (
        contact.get("phone_number") or 
        contact.get("phone") or 
        contact.get("identifier", "")
    )
    
    print(f"[ActionExecutor] _execute_order called")
    print(f"[ActionExecutor] Contact name: {contact_name}")
    print(f"[ActionExecutor] Contact phone: {contact_phone}")
    print(f"[ActionExecutor] Full contact: {contact}")
    
    # Generate order message using conversation history as few-shot examples
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
            
            order_message = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Generate a professional order message for {contact_name}. 
Use the conversation history below as few-shot examples to understand:
- The user's communication style and preferences
- Previous context and details mentioned
- How to structure the order message naturally

Generate a message that:
1. Is professional but matches the conversation tone
2. Includes ALL details from the user's request
3. References relevant context from the conversation if needed
4. Is clear and complete"""
                    },
                    {
                        "role": "system",
                        "content": f"Conversation history (few-shot examples):\n{context_examples}"
                    },
                    {
                        "role": "user",
                        "content": f"User's order request: {request}\n\nGenerate the order message to send to {contact_name}:"
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            message_text = order_message.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ActionExecutor] Error generating order message: {e}")
            message_text = f"Hello, I would like to place an order. {request}"
    else:
        message_text = f"Hello, I would like to place an order. {request}"
    
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
    print(f"[ActionExecutor] 📝 Order message: {message_text[:150]}...")
    print(f"[ActionExecutor] 📝 Full message: {message_text}")
    
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
        response = create_chat(
            phone_numbers=[phone_clean],
            message_text=message_text,
            display_name=contact_name
        )
        
        print(f"[ActionExecutor] ✅ API Response received")
        print(f"[ActionExecutor] ✅ Response data: {json.dumps(response, indent=2)}")
        
        new_chat_id = response.get("chat_id") or response.get("data", {}).get("chat_id")
        print(f"[ActionExecutor] ✅ Order sent successfully! Chat ID: {new_chat_id}")
        
        return {
            "action": "order",
            "success": True,
            "message": f"Order message sent to {contact_name}",
            "chat_id": new_chat_id or response.get("chat_id"),
            "sent_message": message_text
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ActionExecutor] ❌ Error sending order: {e}")
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
    
    # Create chat and send
    try:
        response = create_chat(
            phone_numbers=[contact_phone],
            message_text=message_text,
            display_name=contact_name
        )
        
        return {
            "action": "message",
            "success": True,
            "message": f"Message sent to {contact_name}",
            "chat_id": response.get("chat_id"),
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
        response = create_chat(
            phone_numbers=[contact_phone],
            message_text=message_text,
            display_name=contact_name
        )
        
        return {
            "action": "book",
            "success": True,
            "message": f"Booking request sent to {contact_name}",
            "chat_id": response.get("chat_id"),
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
        response = create_chat(
            phone_numbers=[contact_phone],
            message_text=message_text,
            display_name=contact_name
        )
        
        return {
            "action": "schedule",
            "success": True,
            "message": f"Scheduling request sent to {contact_name}",
            "chat_id": response.get("chat_id"),
            "sent_message": message_text
        }
    except Exception as e:
        return {
            "action": "schedule",
            "success": False,
            "message": f"Failed to send scheduling request to {contact_name}",
            "error": str(e)
        }

