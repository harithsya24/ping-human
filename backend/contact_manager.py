"""Contact management for iMessage conversations.
Contacts are built automatically from incoming messages since Series API doesn't have contact endpoints.
Can also sync from macOS Contacts app."""
import os
import json
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime

load_dotenv()

# JSON file for contact persistence
CONTACTS_JSON_FILE = "contacts_cache.json"

# In-memory contact cache
contacts_cache: Dict[str, dict] = {}
contact_phone_map: Dict[str, str] = {}  # phone -> contact_name

def _load_contacts_from_json():
    """Load contacts from JSON file on startup. Merges with existing cache instead of overwriting."""
    global contacts_cache, contact_phone_map
    
    if os.path.exists(CONTACTS_JSON_FILE):
        try:
            with open(CONTACTS_JSON_FILE, 'r') as f:
                data = json.load(f)
                loaded_contacts = data.get("contacts", {})
                loaded_phone_map = data.get("phone_map", {})
                
                # Merge with existing cache (don't overwrite)
                # Only add contacts that don't already exist
                merged_count = 0
                for name, contact in loaded_contacts.items():
                    if name not in contacts_cache:
                        contacts_cache[name] = contact
                        merged_count += 1
                    else:
                        # Update existing contact with newer info if available
                        existing = contacts_cache[name]
                        if contact.get("last_updated") and existing.get("last_updated"):
                            if contact["last_updated"] > existing["last_updated"]:
                                contacts_cache[name] = contact
                                merged_count += 1
                
                # Merge phone map
                for phone, name in loaded_phone_map.items():
                    if phone not in contact_phone_map:
                        contact_phone_map[phone] = name
                
                print(f"[Contacts] [OK] Loaded {len(loaded_contacts)} contacts from {CONTACTS_JSON_FILE} (merged {merged_count} new contacts)")
        except Exception as e:
            print(f"[Contacts] [WARNING] Error loading contacts from JSON: {e}")
            # Don't clear existing cache on error
    else:
        print(f"[Contacts] [INFO] No contacts cache file found, starting fresh")

def _save_contacts_to_json():
    """Save contacts to JSON file for persistence."""
    try:
        data = {
            "contacts": contacts_cache,
            "phone_map": contact_phone_map,
            "last_updated": datetime.now().isoformat(),
            "total_contacts": len(contacts_cache)
        }
        with open(CONTACTS_JSON_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[Contacts]  Saved {len(contacts_cache)} contacts to {CONTACTS_JSON_FILE}")
    except Exception as e:
        print(f"[Contacts] [WARNING] Error saving contacts to JSON: {e}")

# Load contacts on module import
_load_contacts_from_json()

def fetch_contacts(user_id: Optional[str] = None) -> List[dict]:
    """
    Fetch contacts - builds from cached contacts since Series API doesn't have contact endpoints.
    Contacts are automatically created from incoming messages.
    """
    # Return all cached contacts as a list
    return list(contacts_cache.values())

def get_contact_by_phone(phone: str, user_id: Optional[str] = None) -> Optional[dict]:
    """Get contact information by phone number. Creates contact if not found."""
    # Normalize phone number
    phone_normalized = phone.replace("+", "").replace("-", "").replace(" ", "")
    
    # Check cache first by phone number
    if phone_normalized in contact_phone_map:
        contact_name = contact_phone_map[phone_normalized]
        if contact_name in contacts_cache:
            return contacts_cache[contact_name]
    
    # Check cache by iterating (in case phone format differs)
    for cached_phone, contact_name in contact_phone_map.items():
        if cached_phone == phone_normalized:
            if contact_name in contacts_cache:
                return contacts_cache[contact_name]
    
    # If not found, create a basic contact entry (will be enriched as we receive messages)
    basic_contact = {
        "name": phone,
        "phone_number": phone,
        "display_name": phone,
        "source": "inferred",
        "first_seen": datetime.now().isoformat(),
        "message_count": 0
    }
    contacts_cache[phone] = basic_contact
    contact_phone_map[phone_normalized] = phone
    return basic_contact

def get_contact_name(phone: str, user_id: Optional[str] = None) -> str:
    """Get contact name by phone number, or return phone if not found."""
    contact = get_contact_by_phone(phone, user_id)
    if contact:
        return contact.get("name") or contact.get("display_name") or phone
    return phone

def update_contact_info(phone: str, info: dict, user_id: Optional[str] = None):
    """Update contact information in cache and save to JSON."""
    contact = get_contact_by_phone(phone, user_id)
    if contact:
        # Increment message count
        if "message_count" not in contact:
            contact["message_count"] = 0
        contact["message_count"] = contact.get("message_count", 0) + 1
        
        # Update with new info
        contact.update(info)
        contact["last_updated"] = datetime.now().isoformat()
        contact["last_interaction"] = datetime.now().isoformat()
        
        # Update cache
        contact_name = contact.get("name", phone)
        contacts_cache[contact_name] = contact
        phone_normalized = phone.replace("+", "").replace("-", "").replace(" ", "")
        contact_phone_map[phone_normalized] = contact_name
        
        # Save to JSON (async save to avoid blocking)
        _save_contacts_to_json()

def get_all_contacts() -> List[dict]:
    """Get all cached contacts as a list."""
    return list(contacts_cache.values())

def search_contacts(query: str) -> List[dict]:
    """Search contacts by name or phone number."""
    query_lower = query.lower()
    results = []
    for contact in contacts_cache.values():
        name = (contact.get("name") or "").lower()
        phone = (contact.get("phone_number") or "").lower()
        if query_lower in name or query_lower in phone:
            results.append(contact)
    return results

def add_contact_from_message(phone: str, message_text: str = "", chat_id: str = ""):
    """Add or update a contact from an incoming message."""
    contact = get_contact_by_phone(phone)
    
    # If this is a new contact, try to infer name/category from message context
    if contact.get("source") == "inferred" and message_text:
        # Store message context for later AI analysis
        if "message_context" not in contact:
            contact["message_context"] = []
        contact["message_context"].append({
            "text": message_text[:200],  # Store first 200 chars
            "chat_id": chat_id,
            "timestamp": datetime.now().isoformat()
        })
    
    # Save to JSON
    _save_contacts_to_json()
    
    return contact

def sync_from_macos_contacts(force: bool = False) -> int:
    """Sync contacts from macOS Contacts app and save to JSON.
    
    Args:
        force: If True, sync even if contacts_cache.json exists. 
               If False, skip syncing if cache already exists.
    """
    # If cache exists and force=False, skip syncing
    if not force and os.path.exists(CONTACTS_JSON_FILE) and len(contacts_cache) > 0:
        print(f"[Contacts] [INFO] Contacts cache already exists with {len(contacts_cache)} contacts. Skipping macOS sync. (Use force=True to re-sync)")
        return len(contacts_cache)
    
    try:
        from macos_contacts import sync_macos_contacts_to_cache
        count = sync_macos_contacts_to_cache()
        # Save after syncing
        if count > 0:
            _save_contacts_to_json()
        return count
    except ImportError:
        print("[Contacts] macOS contacts module not available")
        return 0
    except Exception as e:
        print(f"[Contacts] Error syncing macOS contacts: {e}")
        return 0

def get_user_contact_info() -> Optional[dict]:
    """Get the bot owner's (user's) own contact information."""
    sender_number = os.getenv("SENDER_NUMBER", "")
    if sender_number:
        return get_contact_by_phone(sender_number)
    return None

def save_user_contact_info(name: str, phone: str, email: str = "", additional_info: dict = None):
    """Save the user's own contact information to the cache."""
    sender_number = os.getenv("SENDER_NUMBER", phone)
    
    user_contact = {
        "name": name,
        "display_name": name,
        "phone_number": phone or sender_number,
        "email": email,
        "source": "user_self",
        "is_self": True,
        "first_seen": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "message_count": 0
    }
    
    if additional_info:
        user_contact.update(additional_info)
    
    # Update cache
    contacts_cache[name] = user_contact
    phone_normalized = (phone or sender_number).replace("+", "").replace("-", "").replace(" ", "")
    contact_phone_map[phone_normalized] = name
    
    # Save to JSON
    _save_contacts_to_json()
    
    print(f"[Contacts] [OK] Saved user contact info: {name} ({phone or sender_number})")
    return user_contact

def get_contact_for_reply(phone: str) -> dict:
    """Get contact info optimized for reply generation (cached, fast lookup)."""
    contact = get_contact_by_phone(phone)
    if not contact:
        # Return minimal contact info
        return {
            "name": phone,
            "display_name": phone,
            "phone_number": phone,
            "source": "unknown"
        }
    
    # Return essential info for replies
    return {
        "name": contact.get("name") or contact.get("display_name", phone),
        "display_name": contact.get("display_name", contact.get("name", phone)),
        "phone_number": contact.get("phone_number", phone),
        "preferred_language": contact.get("preferred_language", "en"),
        "message_count": contact.get("message_count", 0),
        "last_interaction": contact.get("last_interaction"),
        "source": contact.get("source", "unknown")
    }

