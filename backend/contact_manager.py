"""Contact management for iMessage conversations.
Contacts are built automatically from incoming messages since Series API doesn't have contact endpoints.
Can also sync from macOS Contacts app."""
import os
import json
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime

load_dotenv()

# In-memory contact cache
contacts_cache: Dict[str, dict] = {}
contact_phone_map: Dict[str, str] = {}  # phone -> contact_name

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
    """Update contact information in cache."""
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
    
    return contact

def sync_from_macos_contacts() -> int:
    """Sync contacts from macOS Contacts app."""
    try:
        from macos_contacts import sync_macos_contacts_to_cache
        return sync_macos_contacts_to_cache()
    except ImportError:
        print("[Contacts] macOS contacts module not available")
        return 0
    except Exception as e:
        print(f"[Contacts] Error syncing macOS contacts: {e}")
        return 0

