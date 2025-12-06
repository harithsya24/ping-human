"""Handle location data from messages and convert to addresses."""
import json
import os
from typing import Optional, Dict, Tuple
from user_preferences import set_home_address, get_home_address

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[LocationHandler] [WARNING] requests library not available. Install with: pip install requests")

def extract_location_from_message(data: Dict) -> Optional[Dict]:
    """Extract location data from message event data.
    
    iMessage location data can come in various formats:
    - Direct fields: location, coordinates, lat/lng, latitude/longitude
    - In attachments array
    - In message.attachments
    - In data.attachments
    - As a location share attachment
    
    Returns:
        Dict with 'latitude', 'longitude', 'address' if location found, else None
    """
    # Check for location in various possible fields
    location_data = None
    
    # Check direct location fields in data
    if "location" in data:
        location_data = data["location"]
    elif "coordinates" in data:
        location_data = data["coordinates"]
    elif "lat" in data and "lng" in data:
        location_data = {"latitude": data["lat"], "longitude": data["lng"]}
    elif "latitude" in data and "longitude" in data:
        location_data = {"latitude": data["latitude"], "longitude": data["longitude"]}
    
    # Check in message object if it exists
    message = data.get("message", {})
    if isinstance(message, dict):
        if "location" in message:
            location_data = message["location"]
        elif "coordinates" in message:
            location_data = message["coordinates"]
        elif "lat" in message and "lng" in message:
            location_data = {"latitude": message["lat"], "longitude": message["lng"]}
        elif "latitude" in message and "longitude" in message:
            location_data = {"latitude": message["latitude"], "longitude": message["longitude"]}
    
    # Check in attachments or media (multiple possible locations)
    attachments = data.get("attachments", []) or data.get("message", {}).get("attachments", [])
    if attachments:
        for attachment in attachments:
            # Check if attachment is a location type
            if attachment.get("type") == "location" or attachment.get("mime_type") == "location":
                location_data = attachment.get("location") or attachment
                break
            # Check if attachment has location data
            if "location" in attachment:
                location_data = attachment["location"]
                break
            if "latitude" in attachment or "lat" in attachment:
                location_data = attachment
                break
    
    # Check for location share (iMessage specific)
    if "location_share" in data:
        location_data = data["location_share"]
    elif "message" in data and isinstance(data["message"], dict) and "location_share" in data["message"]:
        location_data = data["message"]["location_share"]
    
    # Check for map item (iMessage map location)
    if "map_item" in data:
        map_item = data["map_item"]
        if isinstance(map_item, dict):
            if "latitude" in map_item or "lat" in map_item:
                location_data = map_item
    
    if location_data:
        lat = location_data.get("latitude") or location_data.get("lat")
        lng = location_data.get("longitude") or location_data.get("lng") or location_data.get("lon")
        
        if lat and lng:
            try:
                return {
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "address": location_data.get("address") or location_data.get("display_name")
                }
            except (ValueError, TypeError):
                print(f"[LocationHandler] [WARNING] Invalid location coordinates: lat={lat}, lng={lng}")
                return None
    
    return None

def reverse_geocode(latitude: float, longitude: float) -> Optional[str]:
    """Convert coordinates to address using reverse geocoding.
    
    Uses OpenStreetMap Nominatim API (free, no API key required).
    """
    if not REQUESTS_AVAILABLE:
        print("[LocationHandler] [WARNING] Cannot reverse geocode - requests library not available")
        return None
    
    try:
        # Use OpenStreetMap Nominatim API (free, no key required)
        url = f"https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1
        }
        headers = {
            "User-Agent": "PingHumans-Bot/1.0"  # Required by Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get("display_name")
            if address:
                print(f"[LocationHandler] [OK] Reverse geocoded: {latitude}, {longitude} → {address}")
                return address
            else:
                print(f"[LocationHandler] [WARNING] No address found in geocoding response")
                return None
        else:
            print(f"[LocationHandler] [WARNING] Geocoding API error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[LocationHandler] [WARNING] Error reverse geocoding: {e}")
        return None

def process_location_message(data: Dict, save_as_home: bool = False) -> Optional[str]:
    """Process location from message and return address.
    
    Args:
        data: Message event data
        save_as_home: If True, save the address as home address
    
    Returns:
        Address string if location found and converted, else None
    """
    location = extract_location_from_message(data)
    
    if not location:
        return None
    
    lat = location.get("latitude")
    lng = location.get("longitude")
    address = location.get("address")
    
    # If address not provided, reverse geocode
    if not address and lat and lng:
        address = reverse_geocode(lat, lng)
    
    if address:
        # Save as home address if requested
        if save_as_home:
            set_home_address(address)
            print(f"[LocationHandler] 🏠 Saved location as home address: {address}")
        
        return address
    
    return None

def is_location_message(data: Dict) -> bool:
    """Check if message contains location data."""
    return extract_location_from_message(data) is not None

def format_location_for_delivery(latitude: float, longitude: float, address: Optional[str] = None) -> str:
    """Format location for delivery message.
    
    If address is provided, use it. Otherwise, use coordinates.
    """
    if address:
        return address
    else:
        return f"Coordinates: {latitude}, {longitude}"

