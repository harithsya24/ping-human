"""Track pending actions that need user confirmation or details."""
from typing import Dict, Optional
from datetime import datetime
from collections import defaultdict

# Track pending confirmations: chat_id -> pending_action_info
pending_confirmations: Dict[str, Dict] = {}

# Track pending details collection: chat_id -> action_info
pending_details: Dict[str, Dict] = {}

def set_pending_confirmation(chat_id: str, action_info: Dict):
    """Set a pending confirmation for a chat."""
    pending_confirmations[chat_id] = {
        **action_info,
        "timestamp": datetime.now().isoformat(),
        "type": "confirmation"
    }

def get_pending_confirmation(chat_id: str) -> Optional[Dict]:
    """Get pending confirmation for a chat."""
    return pending_confirmations.get(chat_id)

def clear_pending_confirmation(chat_id: str):
    """Clear pending confirmation for a chat."""
    if chat_id in pending_confirmations:
        del pending_confirmations[chat_id]

def set_pending_details(chat_id: str, action_info: Dict):
    """Set pending details collection for a chat."""
    pending_details[chat_id] = {
        **action_info,
        "timestamp": datetime.now().isoformat(),
        "type": "details"
    }

def get_pending_details(chat_id: str) -> Optional[Dict]:
    """Get pending details collection for a chat."""
    return pending_details.get(chat_id)

def clear_pending_details(chat_id: str):
    """Clear pending details for a chat."""
    if chat_id in pending_details:
        del pending_details[chat_id]

def is_confirmation_response(text: str) -> bool:
    """Check if text is a confirmation (yes, ok, proceed, etc.)."""
    confirmation_words = ["yes", "yep", "yeah", "ok", "okay", "sure", "proceed", "go ahead", "confirm", "do it"]
    text_lower = text.lower().strip()
    return any(word in text_lower for word in confirmation_words)

