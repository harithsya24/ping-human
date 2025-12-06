"""Action history tracking functionality."""
import json
import os
import uuid
from datetime import datetime, timezone
from threading import Lock

ACTION_HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "action_history.json")
_history_lock = Lock()

def _load_history():
    """Load action history from file or return empty list."""
    if os.path.exists(ACTION_HISTORY_FILE):
        try:
            with open(ACTION_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ActionHistory] Error loading: {e}")
    return []

def _save_history(history):
    """Save action history to file."""
    try:
        with open(ACTION_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"[ActionHistory] Error saving: {e}")

def log_action(action_type, details):
    """Log an action to the history file."""
    with _history_lock:
        history = _load_history()
        
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "details": details
        }
        
        history.append(entry)
        _save_history(history)

def get_action_history(action_type=None, limit=None):
    """Get action history, optionally filtered by type and limited."""
    with _history_lock:
        history = _load_history()
        
        if action_type:
            history = [entry for entry in history if entry.get("action_type") == action_type]
        
        if limit:
            history = history[-limit:]
        
        return history

def get_action_summary(entry):
    """Generate a summary string for an action entry."""
    action_type = entry.get("action_type", "")
    details = entry.get("details", {})
    
    if action_type == "message_sent":
        to = details.get("to", "Unknown")
        message_preview = details.get("message", "")[:50]
        return f"Sent to {to}: {message_preview}..."
    elif action_type == "message_received":
        from_contact = details.get("from", "Unknown")
        message_preview = details.get("message", "")[:50]
        return f"From {from_contact}: {message_preview}..."
    elif action_type == "order_placed" or action_type == "order":
        contact = details.get("contact", "Unknown")
        item = details.get("item", "order")
        return f"Order: {item} to {contact}"
    elif action_type == "booking_created" or action_type == "book":
        contact = details.get("contact", "Unknown")
        service = details.get("service", "appointment")
        return f"Booking: {service} with {contact}"
    elif action_type == "reminder_sent":
        reminder_type = details.get("type", "reminder")
        return f"Reminder sent: {reminder_type}"
    elif action_type == "ai_action" or action_type == "agent_response":
        action = details.get("action", "action")
        return f"AI action: {action}"
    elif action_type == "call":
        contact = details.get("contact", "Unknown")
        return f"Call: {contact}"
    elif action_type == "message":
        contact = details.get("contact", "Unknown")
        return f"Message sent to {contact}"
    elif action_type == "follow_up_sent":
        recipient = details.get("recipient", "Unknown")
        return f"Follow-up sent to {recipient}"
    elif action_type == "error":
        error_type = details.get("error_type", "Error")
        return f"Error: {error_type}"
    else:
        return f"{action_type}: {str(details)[:50]}"

def get_action_status(entry):
    """Get status for an action entry."""
    action_type = entry.get("action_type", "")
    details = entry.get("details", {})
    
    if action_type == "error":
        return "error"
    elif details.get("success") is False:
        return "failed"
    elif details.get("success") is True:
        return "success"
    else:
        return "pending"

