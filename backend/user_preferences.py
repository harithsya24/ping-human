"""User preferences and address storage."""
import json
import os
from typing import Optional, Dict
from datetime import datetime

USER_PREFERENCES_FILE = "user_preferences.json"

# Default preferences structure
DEFAULT_PREFERENCES = {
    "addresses": {
        "home": None,
        "work": None,
        "other": []
    },
    "preferences": {
        "default_delivery_address": "home",
        "preferred_payment_method": None
    },
    "last_updated": None
}

def _load_preferences() -> Dict:
    """Load user preferences from JSON file."""
    if os.path.exists(USER_PREFERENCES_FILE):
        try:
            with open(USER_PREFERENCES_FILE, 'r') as f:
                prefs = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged = DEFAULT_PREFERENCES.copy()
                merged.update(prefs)
                if "addresses" not in merged:
                    merged["addresses"] = DEFAULT_PREFERENCES["addresses"].copy()
                return merged
        except Exception as e:
            print(f"[UserPreferences] [WARNING] Error loading preferences: {e}")
            return DEFAULT_PREFERENCES.copy()
    return DEFAULT_PREFERENCES.copy()

def _save_preferences(prefs: Dict):
    """Save user preferences to JSON file."""
    try:
        prefs["last_updated"] = datetime.now().isoformat()
        with open(USER_PREFERENCES_FILE, 'w') as f:
            json.dump(prefs, f, indent=2)
        print(f"[UserPreferences]  Saved user preferences")
    except Exception as e:
        print(f"[UserPreferences] [WARNING] Error saving preferences: {e}")

def get_home_address() -> Optional[str]:
    """Get user's home address."""
    prefs = _load_preferences()
    return prefs.get("addresses", {}).get("home")

def set_home_address(address: str):
    """Set user's home address."""
    prefs = _load_preferences()
    if "addresses" not in prefs:
        prefs["addresses"] = {}
    prefs["addresses"]["home"] = address
    _save_preferences(prefs)
    print(f"[UserPreferences] [OK] Home address saved")

def get_address_for_keyword(keyword: str) -> Optional[str]:
    """Get address for a keyword (home, work, etc.)."""
    keyword_lower = keyword.lower().strip()
    prefs = _load_preferences()
    addresses = prefs.get("addresses", {})
    
    if keyword_lower == "home":
        return addresses.get("home")
    elif keyword_lower == "work":
        return addresses.get("work")
    else:
        # Check other addresses
        other_addresses = addresses.get("other", [])
        for addr in other_addresses:
            if keyword_lower in addr.get("name", "").lower():
                return addr.get("address")
    
    return None

def has_address(keyword: str) -> bool:
    """Check if user has an address for a keyword."""
    return get_address_for_keyword(keyword) is not None

def extract_address_from_text(text: str) -> Optional[str]:
    """Extract address information from user text."""
    text_lower = text.lower()
    
    # Check for "home" keyword
    if "home" in text_lower:
        home_addr = get_home_address()
        if home_addr:
            return home_addr
        return "home"  # Return keyword if address not set
    
    # Check for "work" keyword
    if "work" in text_lower:
        prefs = _load_preferences()
        work_addr = prefs.get("addresses", {}).get("work")
        if work_addr:
            return work_addr
        return "work"
    
    # Try to extract address from text (look for patterns like street numbers, zip codes, etc.)
    # This is a simple extraction - can be enhanced with NLP
    address_indicators = ["street", "avenue", "ave", "road", "rd", "drive", "dr", "lane", "ln", "blvd", "boulevard", "zip", "zipcode"]
    if any(indicator in text_lower for indicator in address_indicators):
        # Return the text as potential address
        return text
    
    return None

def get_all_addresses() -> Dict:
    """Get all stored addresses."""
    prefs = _load_preferences()
    return prefs.get("addresses", {})

