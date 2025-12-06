"""Contact management for iMessage conversations."""
import os
import json
import requests
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime

load_dotenv()

BASE_URL = os.getenv("SERIES_API_BASE_URL")
API_KEY = os.getenv("SERIES_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def _url(path: str) -> str:
    return BASE_URL.rstrip("/") + path

# In-memory contact cache
contacts_cache: Dict[str, dict] = {}
contact_phone_map: Dict[str, str] = {}  # phone -> contact_name

def fetch_contacts(user_id: Optional[str] = None) -> List[dict]:
    """Fetch contacts from Series API."""
    try:
        # Try to get contacts via user connections endpoint
        if user_id:
            r = requests.get(_url(f"/api/users/{user_id}/connections"), headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                connections = data.get("connections", data.get("data", []))
                return connections
        
        # Fallback: try general contacts endpoint
        try:
            r = requests.get(_url("/api/contacts"), headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        
        return []
    except Exception as e:
        print(f"[Contacts] Error fetching contacts: {e}")
        return []

def get_contact_by_phone(phone: str, user_id: Optional[str] = None) -> Optional[dict]:
    """Get contact information by phone number."""
    # Normalize phone number
    phone = phone.replace("+", "").replace("-", "").replace(" ", "")
    
    # Check cache first
    if phone in contact_phone_map:
        contact_name = contact_phone_map[phone]
        if contact_name in contacts_cache:
            return contacts_cache[contact_name]
    
    # Try to fetch from API
    contacts = fetch_contacts(user_id)
    for contact in contacts:
        contact_phone = contact.get("phone_number", "").replace("+", "").replace("-", "").replace(" ", "")
        if contact_phone == phone:
            contact_name = contact.get("name", contact.get("display_name", phone))
            contacts_cache[contact_name] = contact
            contact_phone_map[phone] = contact_name
            return contact
    
    # If not found, create a basic contact entry
    basic_contact = {
        "name": phone,
        "phone_number": phone,
        "display_name": phone,
        "source": "inferred"
    }
    contacts_cache[phone] = basic_contact
    contact_phone_map[phone] = phone
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
        contact.update(info)
        contact["last_updated"] = datetime.now().isoformat()
        contacts_cache[contact.get("name", phone)] = contact

def get_all_contacts() -> Dict[str, dict]:
    """Get all cached contacts."""
    return contacts_cache.copy()

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

