"""Series API client for sending messages."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("SERIES_API_BASE_URL")
API_KEY = os.getenv("SERIES_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def _url(path: str) -> str:
    return BASE_URL.rstrip("/") + path

def send_message(chat_id: int, text: str):
    """Send a message to a chat."""
    payload = {"message": {"text": text}}
    r = requests.post(_url(f"/api/chats/{chat_id}/chat_messages"), headers=HEADERS, json=payload)
    
    # Check for rate limits or quotas
    if r.status_code == 429:
        print(f"[API] Rate limit exceeded! Status: {r.status_code}")
        print(f"[API] Response: {r.text}")
        raise Exception(f"Rate limit exceeded: {r.text}")
    elif r.status_code == 403:
        print(f"[API] Forbidden - possible quota exceeded! Status: {r.status_code}")
        print(f"[API] Response: {r.text}")
        raise Exception(f"Quota exceeded or forbidden: {r.text}")
    elif r.status_code >= 400:
        print(f"[API] Error sending message: {r.status_code}")
        print(f"[API] Response: {r.text}")
    
    r.raise_for_status()
    return r.json()

def create_chat(phone_numbers: list, message_text: str, display_name: str = None):
    """Create a new chat and send initial message."""
    sender = os.getenv("SENDER_NUMBER")
    
    # Clean phone numbers - remove any invalid entries
    cleaned_phones = []
    for phone in phone_numbers:
        if phone and phone.strip():
            # Remove "missing value" if present
            phone_clean = phone.replace("missing value", "").strip()
            if phone_clean:
                cleaned_phones.append(phone_clean)
    
    if not cleaned_phones:
        raise ValueError("No valid phone numbers provided")
    
    payload = {
        "send_from": sender,
        "chat": {"phone_numbers": cleaned_phones},
        "message": {"text": message_text}
    }
    if display_name and "missing value" not in display_name.lower():
        payload["chat"]["display_name"] = display_name
    
    print(f"[API] Creating chat with phones: {cleaned_phones}, display_name: {display_name}")
    print(f"[API] Payload: {json.dumps(payload, indent=2)}")
    
    r = requests.post(_url("/api/chats"), headers=HEADERS, json=payload)
    
    # Check for rate limits or quotas
    if r.status_code == 429:
        print(f"[API] Rate limit exceeded! Status: {r.status_code}")
        print(f"[API] Response: {r.text}")
        raise Exception(f"Rate limit exceeded: {r.text}")
    elif r.status_code == 403:
        print(f"[API] Forbidden - possible quota exceeded or invalid phone number! Status: {r.status_code}")
        print(f"[API] Response: {r.text}")
        print(f"[API] Phone numbers attempted: {cleaned_phones}")
        raise Exception(f"Forbidden (403): {r.text}. Check if phone numbers are valid and API quota is available.")
    elif r.status_code >= 400:
        print(f"[API] Error creating chat: {r.status_code}")
        print(f"[API] Response: {r.text}")
    
    r.raise_for_status()
    return r.json()

def get_user_connections(user_id: str):
    """Get connections for a specific user with better error handling."""
    try:
        r = requests.get(_url(f"/api/users/{user_id}/connections"), headers=HEADERS, timeout=10)
        
        # Check for rate limits
        if r.status_code == 429:
            print(f"[API] Rate limit exceeded for user connections! Status: {r.status_code}")
            raise Exception(f"Rate limit exceeded: {r.text}")
        elif r.status_code == 403:
            print(f"[API] Forbidden - possible quota exceeded! Status: {r.status_code}")
            raise Exception(f"Quota exceeded or forbidden: {r.text}")
        elif r.status_code == 404:
            print(f"[API] User {user_id} not found")
            return {"error": "User not found", "user_id": user_id, "connections": []}
        elif r.status_code >= 400:
            print(f"[API] Error getting user connections: {r.status_code}")
            print(f"[API] Response: {r.text}")
            raise Exception(f"API error: {r.status_code} - {r.text}")
        
        r.raise_for_status()
        data = r.json()
        
        # Format response for better usability
        if isinstance(data, dict):
            return {
                "user_id": user_id,
                "connections": data.get("connections", data.get("data", [])),
                "count": len(data.get("connections", data.get("data", []))),
                "status": "success"
            }
        elif isinstance(data, list):
            return {
                "user_id": user_id,
                "connections": data,
                "count": len(data),
                "status": "success"
            }
        return data
    except requests.exceptions.Timeout:
        print(f"[API] Timeout getting connections for user {user_id}")
        return {"error": "Request timeout", "user_id": user_id, "connections": []}
    except requests.exceptions.RequestException as e:
        print(f"[API] Request error getting connections: {e}")
        return {"error": str(e), "user_id": user_id, "connections": []}
    except Exception as e:
        print(f"[API] Error getting user connections: {e}")
        return {"error": str(e), "user_id": user_id, "connections": []}

