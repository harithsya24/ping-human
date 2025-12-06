"""Permission management for contact access and other features."""
from typing import Dict, Optional
from datetime import datetime
import json
import os
from threading import Lock

# Permission storage
# Store in project root (parent directory)
PERMISSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "permissions.json")
_permissions_lock = Lock()

# Default permissions structure
_default_permissions = {
    "contacts": {
        "granted": False,
        "requested": False,
        "requested_at": None,
        "granted_at": None,
        "user_response": None
    },
    "actions": {
        "granted": False,
        "requested": False,
        "requested_at": None,
        "granted_at": None,
        "user_response": None
    }
}

def _load_permissions() -> Dict:
    """Load permissions from file."""
    if not os.path.exists(PERMISSIONS_FILE):
        return _default_permissions.copy()
    
    try:
        with open(PERMISSIONS_FILE, 'r') as f:
            data = json.load(f)
            # Ensure all keys exist
            for key in _default_permissions:
                if key not in data:
                    data[key] = _default_permissions[key].copy()
            return data
    except Exception as e:
        print(f"[Permissions] Error loading permissions: {e}")
        return _default_permissions.copy()

def _save_permissions(permissions: Dict):
    """Save permissions to file."""
    try:
        with _permissions_lock:
            with open(PERMISSIONS_FILE, 'w') as f:
                json.dump(permissions, f, indent=2)
    except Exception as e:
        print(f"[Permissions] Error saving permissions: {e}")

def request_contact_permission(chat_id: str, user_phone: str) -> Dict:
    """Request permission to access contacts."""
    permissions = _load_permissions()
    
    if permissions["contacts"]["granted"]:
        return {
            "granted": True,
            "message": "Contact access already granted"
        }
    
    if permissions["contacts"]["requested"]:
        return {
            "granted": False,
            "requested": True,
            "message": "Contact access permission already requested. Please respond with 'yes' or 'allow' to grant access."
        }
    
    # Mark as requested
    permissions["contacts"]["requested"] = True
    permissions["contacts"]["requested_at"] = datetime.now().isoformat()
    _save_permissions(permissions)
    
    return {
        "granted": False,
        "requested": True,
        "message": "📱 iPhone Contact Access Required\n\nI need permission to use your iPhone contacts to help with actions like:\n• Ordering (pizza, food, etc.)\n• Booking (hotels, appointments)\n• Calling contacts\n• Finding services\n\nYour contacts are extracted from iMessage data. Reply 'yes' or 'allow' to grant access."
    }

def grant_contact_permission(chat_id: str, user_phone: str) -> Dict:
    """Grant contact access permission."""
    permissions = _load_permissions()
    permissions["contacts"]["granted"] = True
    permissions["contacts"]["granted_at"] = datetime.now().isoformat()
    permissions["contacts"]["user_response"] = "granted"
    _save_permissions(permissions)
    
    return {
        "granted": True,
        "message": "✅ Contact access granted!"
    }

def deny_contact_permission(chat_id: str, user_phone: str) -> Dict:
    """Deny contact access permission."""
    permissions = _load_permissions()
    permissions["contacts"]["granted"] = False
    permissions["contacts"]["user_response"] = "denied"
    _save_permissions(permissions)
    
    return {
        "granted": False,
        # "message": "Contact access denied. I won't be able to use your contacts for actions."
        "message": ""  # Commented out - don't send message when permission denied
    }

def check_contact_permission() -> bool:
    """Check if contact access is granted."""
    permissions = _load_permissions()
    return permissions["contacts"].get("granted", False)

def has_contact_permission() -> bool:
    """Check if contact permission is granted (alias)."""
    return check_contact_permission()

def get_permission_status() -> Dict:
    """Get current permission status."""
    permissions = _load_permissions()
    return {
        "contacts": {
            "granted": permissions["contacts"].get("granted", False),
            "requested": permissions["contacts"].get("requested", False),
            "requested_at": permissions["contacts"].get("requested_at"),
            "granted_at": permissions["contacts"].get("granted_at")
        },
        "actions": {
            "granted": permissions["actions"].get("granted", False),
            "requested": permissions["actions"].get("requested", False),
            "requested_at": permissions["actions"].get("requested_at"),
            "granted_at": permissions["actions"].get("granted_at")
        }
    }

def reset_permissions():
    """Reset all permissions (for testing)."""
    permissions = _default_permissions.copy()
    _save_permissions(permissions)
    return {"message": "All permissions reset"}

def process_permission_response(text: str, chat_id: str, user_phone: str) -> Optional[Dict]:
    """Process user response to permission request."""
    text_lower = text.lower().strip()
    
    # Check for grant keywords
    grant_keywords = ["yes", "allow", "grant", "ok", "okay", "sure", "permit", "enable"]
    deny_keywords = ["no", "deny", "refuse", "reject", "disable", "don't", "dont"]
    
    if any(keyword in text_lower for keyword in grant_keywords):
        return grant_contact_permission(chat_id, user_phone)
    elif any(keyword in text_lower for keyword in deny_keywords):
        return deny_contact_permission(chat_id, user_phone)
    
    return None

