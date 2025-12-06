"""Intelligent contact matching for user requests."""
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from contact_manager import get_all_contacts, search_contacts, get_contact_by_phone

def match_contact_to_request(request: str, ai_client: Optional[OpenAI] = None, exclude_phone: Optional[str] = None) -> Optional[Dict]:
    """Match a user request to the best contact in the contact list."""
    contacts = get_all_contacts()
    
    if not contacts:
        return None
    
    # get_all_contacts() already returns a list
    contacts_list = contacts if isinstance(contacts, list) else list(contacts.values())
    
    # Filter out the user's own contact and generic phone number contacts
    filtered_contacts = []
    for contact in contacts_list:
        phone = contact.get("phone_number", "")
        name = contact.get("name") or contact.get("display_name", "")
        
        # Exclude user's own phone
        if exclude_phone:
            phone_normalized = phone.replace("+", "").replace("-", "").replace(" ", "")
            exclude_normalized = exclude_phone.replace("+", "").replace("-", "").replace(" ", "")
            if phone_normalized == exclude_normalized:
                continue
        
        # Exclude contacts that are just phone numbers (not real names)
        # If name is just a phone number format, skip it unless it has meaningful metadata
        if name and (name.startswith("+") or name.replace("(", "").replace(")", "").replace("-", "").replace(" ", "").isdigit()):
            # Only include if it has category metadata suggesting it's a business
            if not contact.get("metadata") and contact.get("source") != "iphone_message":
                continue
        
        filtered_contacts.append(contact)
    
    if not filtered_contacts:
        return None
    
    contacts_list = filtered_contacts
    
    if not ai_client:
        # Fallback: simple keyword matching
        return _simple_contact_match(request, contacts_list)
    
    # Use AI to intelligently match request to contact
    try:
        # Build contact descriptions
        contact_descriptions = []
        for contact in contacts_list:
            name = contact.get("name") or contact.get("display_name", "Unknown")
            phone = contact.get("phone_number", "")
            # Include any metadata that might help
            metadata = contact.get("metadata", {})
            description = f"Name: {name}, Phone: {phone}"
            if metadata:
                description += f", Metadata: {metadata}"
            contact_descriptions.append(description)
        
        contacts_text = "\n".join([f"{i+1}. {desc}" for i, desc in enumerate(contact_descriptions)])
        
        system_prompt = """You are a contact matching assistant. Given a user request and a list of contacts, 
identify which contact is most relevant to fulfill the request.

IMPORTANT RULES:
- Do NOT match the user's own contact or phone number
- Do NOT match generic phone numbers without meaningful names
- Only match contacts that are clearly related to the request (e.g., "pizza" request → pizza restaurant, not random contacts)
- If no contact clearly matches, return "0"

Examples:
- Request: "order pizza" → Match to pizza restaurant contact (NOT user's own phone)
- Request: "call my doctor" → Match to doctor/medical contact
- Request: "book a hotel" → Match to hotel contact
- Request: "schedule appointment" → Match to service provider contact

Return ONLY the contact number (1, 2, 3, etc.) that best matches the request.
If no contact matches, return "0"."""
        
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Request: {request}\n\nContacts:\n{contacts_text}\n\nWhich contact number matches this request? (Return only the number)"}
            ],
            temperature=0.3,
            max_tokens=10
        )
        
        match_result = response.choices[0].message.content.strip()
        
        # Parse the result
        try:
            contact_index = int(match_result) - 1
            if 0 <= contact_index < len(contacts_list):
                matched_contact = contacts_list[contact_index]
                confidence = _calculate_match_confidence(request, matched_contact, ai_client)
                return {
                    "contact": matched_contact,
                    "confidence": confidence,
                    "match_reason": f"AI matched based on request: {request}"
                }
        except ValueError:
            pass
        
        # If AI matching failed, fall back to simple matching
        return _simple_contact_match(request, contacts_list, exclude_phone)
        
    except Exception as e:
        print(f"[ContactMatcher] AI matching error: {e}")
        return _simple_contact_match(request, contacts_list, exclude_phone)

def _simple_contact_match(request: str, contacts: List[Dict], exclude_phone: Optional[str] = None) -> Optional[Dict]:
    """Simple keyword-based contact matching."""
    request_lower = request.lower()
    
    # Extract keywords from request (remove action words)
    action_words = ["order", "buy", "get", "call", "book", "schedule", "find", "contact", "message", "text", "my", "a", "the"]
    keywords = [word for word in request_lower.split() if word not in action_words]
    
    if not keywords:
        return None
    
    best_match = None
    best_score = 0
    
    for contact in contacts:
        # Skip if this is the excluded phone
        if exclude_phone:
            phone = contact.get("phone_number", "")
            phone_normalized = phone.replace("+", "").replace("-", "").replace(" ", "")
            exclude_normalized = exclude_phone.replace("+", "").replace("-", "").replace(" ", "")
            if phone_normalized == exclude_normalized:
                continue
        name = (contact.get("name") or contact.get("display_name", "")).lower()
        phone = (contact.get("phone_number", "")).lower()
        metadata = contact.get("metadata", {})
        
        score = 0
        
        # Check name matches
        for keyword in keywords:
            if keyword in name:
                score += 2
            if keyword in phone:
                score += 1
        
        # Check metadata
        for key, value in metadata.items():
            value_str = str(value).lower()
            for keyword in keywords:
                if keyword in value_str:
                    score += 1
        
        if score > best_score:
            best_score = score
            best_match = contact
    
    if best_match and best_score > 0:
        return {
            "contact": best_match,
            "confidence": min(best_score / 10.0, 1.0),
            "match_reason": f"Keyword match (score: {best_score})"
        }
    
    return None

def _calculate_match_confidence(request: str, contact: Dict, ai_client: OpenAI) -> float:
    """Calculate confidence score for a contact match."""
    try:
        name = contact.get("name") or contact.get("display_name", "")
        
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Rate how well this contact matches the request on a scale of 0.0 to 1.0. Return only the number."},
                {"role": "user", "content": f"Request: {request}\nContact: {name}\n\nConfidence (0.0-1.0):"}
            ],
            temperature=0.2,
            max_tokens=5
        )
        
        confidence = float(response.choices[0].message.content.strip())
        return max(0.0, min(1.0, confidence))
    except:
        return 0.5  # Default confidence

def find_contacts_by_category(category: str, contacts: Optional[List[Dict]] = None, ai_client: Optional[OpenAI] = None) -> List[Dict]:
    """Find contacts by category (restaurant, medical, service, etc.)."""
    if contacts is None:
        contacts = get_all_contacts()
        # Ensure it's a list
        if not isinstance(contacts, list):
            contacts = list(contacts.values())
    
    category_lower = category.lower()
    matches = []
    
    # Category keywords
    category_keywords = {
        "restaurant": ["pizza", "food", "restaurant", "cafe", "diner", "bistro"],
        "medical": ["doctor", "hospital", "clinic", "medical", "health", "physician"],
        "service": ["service", "repair", "plumber", "electrician", "mechanic"],
        "hotel": ["hotel", "lodging", "accommodation", "inn"],
        "retail": ["store", "shop", "retail", "market"]
    }
    
    keywords = category_keywords.get(category_lower, [category_lower])
    
    for contact in contacts:
        name = (contact.get("name") or contact.get("display_name", "")).lower()
        for keyword in keywords:
            if keyword in name:
                matches.append(contact)
                break
    
    return matches

def get_contact_suggestions(request: str, limit: int = 3) -> List[Dict]:
    """Get multiple contact suggestions for a request."""
    contacts = get_all_contacts()
    # Ensure it's a list
    if not isinstance(contacts, list):
        contacts = list(contacts.values())
    
    if not contacts:
        return []
    
    # Simple scoring approach
    request_lower = request.lower()
    scored_contacts = []
    
    for contact in contacts:
        name = (contact.get("name") or contact.get("display_name", "")).lower()
        score = 0
        
        # Check if request keywords match contact name
        request_words = request_lower.split()
        for word in request_words:
            if word in name:
                score += len(word)  # Longer matches score higher
        
        if score > 0:
            scored_contacts.append((score, contact))
    
    # Sort by score and return top matches
    scored_contacts.sort(reverse=True, key=lambda x: x[0])
    return [contact for _, contact in scored_contacts[:limit]]

