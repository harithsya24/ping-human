"""Strict messaging, memory, reminder, and mail checker rules enforcement."""
import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

RECIPIENT_NUMBER = os.getenv("RECIPIENT_NUMBER", "+12017056654")

def get_allowed_recipient() -> str:
    """Get the only allowed recipient phone number for messages."""
    return RECIPIENT_NUMBER

def validate_recipient(phone_number: str) -> bool:
    """Validate that phone number matches the allowed recipient."""
    normalized_allowed = _normalize_phone(RECIPIENT_NUMBER)
    normalized_input = _normalize_phone(phone_number)
    return normalized_input == normalized_allowed

def enforce_recipient(phone_numbers: List[str]) -> List[str]:
    """Enforce that only the allowed recipient is used. Returns list with only allowed recipient."""
    allowed = get_allowed_recipient()
    if allowed not in phone_numbers:
        return [allowed]
    return [allowed]

def _normalize_phone(phone: str) -> str:
    """Normalize phone number for comparison."""
    if not phone:
        return ""
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return phone

def validate_message_storage(message_data: Dict[str, Any]) -> bool:
    """Validate that message data is clean and contains only real data (no hallucination)."""
    required_fields = ["sender", "text", "timestamp"]
    for field in required_fields:
        if field not in message_data:
            return False
    
    if not message_data.get("text") or not isinstance(message_data.get("text"), str):
        return False
    
    if not message_data.get("timestamp") or not isinstance(message_data.get("timestamp"), str):
        return False
    
    return True

def get_non_hallucination_response() -> str:
    """Get the standard response when information is not in JSON history."""
    return "I cannot find that information in the stored conversation history."

def is_reminder_message(message: str) -> bool:
    """Check if a message is a reminder (should be kept separate from conversation logs)."""
    reminder_indicators = [
        "reminder", "meeting", "appointment", "urgent email", "alert",
        "📅", "🚨", "⏰", "📆", "🔔"
    ]
    message_lower = message.lower()
    return any(indicator in message_lower for indicator in reminder_indicators)

def is_email_summary(message: str) -> bool:
    """Check if a message is an email summary (should be kept separate from conversation logs)."""
    email_indicators = [
        "urgent email", "email alert", "📧", "inbox", "gmail",
        "from:", "subject:", "email from"
    ]
    message_lower = message.lower()
    return any(indicator in message_lower for indicator in email_indicators)

def should_separate_from_conversation(message: str) -> bool:
    """Check if a message should be kept separate from conversation logs."""
    return is_reminder_message(message) or is_email_summary(message)

def validate_json_context(context: Any) -> bool:
    """Validate that context is valid JSON data (not hallucinated)."""
    if context is None:
        return False
    
    if isinstance(context, dict):
        if "messages" in context:
            messages = context["messages"]
            if isinstance(messages, list):
                for msg in messages:
                    if not isinstance(msg, dict):
                        return False
                    if not validate_message_storage(msg):
                        return False
        return True
    
    if isinstance(context, list):
        for item in context:
            if not isinstance(item, dict):
                return False
            if not validate_message_storage(item):
                return False
        return True
    
    return False

def enforce_context_usage_only() -> str:
    """Get instruction for using ONLY provided JSON context."""
    return """STRICT RULE: Use ONLY the provided JSON CONTEXT to answer.
- Do NOT rewrite the logs
- Do NOT impersonate the user or receiver
- Do NOT continue old conversation threads
- Do NOT create or invent any information not in the JSON
- If information is missing, respond: "I cannot find that information in the stored conversation history."
"""
