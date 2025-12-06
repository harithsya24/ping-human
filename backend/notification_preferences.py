"""User notification preferences management."""
import json
import os
from typing import Dict, Optional
from threading import Lock

PREFERENCES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notification_preferences.json")
_preferences_lock = Lock()

DEFAULT_PREFERENCES = {
    "proactive_meeting_reminders": True,
    "proactive_urgent_emails": True,
    "meeting_reminder_times": ["1h", "30m", "5m"],
    "urgent_email_limit": 3,
    "enable_all_proactive": True
}

def _load_preferences() -> Dict:
    """Load preferences from file."""
    if os.path.exists(PREFERENCES_FILE):
        try:
            with open(PREFERENCES_FILE, 'r') as f:
                return json.load(f)
        except:
            return DEFAULT_PREFERENCES.copy()
    return DEFAULT_PREFERENCES.copy()

def _save_preferences(prefs: Dict):
    """Save preferences to file."""
    try:
        with open(PREFERENCES_FILE, 'w') as f:
            json.dump(prefs, f, indent=2)
    except Exception as e:
        print(f"[NotificationPrefs] Error saving: {e}")

def get_preferences() -> Dict:
    """Get current notification preferences."""
    with _preferences_lock:
        return _load_preferences()

def update_preferences(**kwargs) -> Dict:
    """Update notification preferences."""
    with _preferences_lock:
        prefs = _load_preferences()
        prefs.update(kwargs)
        _save_preferences(prefs)
        return prefs

def should_send_proactive_reminder(reminder_type: str) -> bool:
    """Check if proactive reminder should be sent."""
    prefs = get_preferences()
    
    if not prefs.get("enable_all_proactive", True):
        return False
    
    if reminder_type == "meeting":
        return prefs.get("proactive_meeting_reminders", True)
    elif reminder_type == "urgent_email":
        return prefs.get("proactive_urgent_emails", True)
    
    return False

def get_reminder_times() -> list:
    """Get configured reminder times."""
    prefs = get_preferences()
    return prefs.get("meeting_reminder_times", ["1h", "30m", "5m"])

def get_urgent_email_limit() -> int:
    """Get limit for urgent email notifications."""
    prefs = get_preferences()
    return prefs.get("urgent_email_limit", 3)

