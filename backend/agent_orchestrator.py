"""Multi-agent orchestrator for intelligent contact-based actions."""
from typing import Dict, Optional, List, Tuple
from openai import OpenAI
from contact_matcher import match_contact_to_request, get_contact_suggestions
from action_executor import execute_action
from conversation_tracker import get_conversation_thread
from permission_manager import check_contact_permission, request_contact_permission

def process_user_request(
    request: str,
    chat_id: str,
    user_phone: Optional[str] = None,
    ai_client: Optional[OpenAI] = None
) -> Dict:
    """Process a user request and execute appropriate action using contacts."""
    
    # Step 0: Check if contact permission is granted
    if not check_contact_permission():
        # Request permission first
        permission_request = request_contact_permission(chat_id, user_phone or "unknown")
        return {
            "success": False,
            "needs_permission": True,
            "permission_type": "contacts",
            "message": permission_request.get("message", "Permission required to access contacts"),
            "requested": permission_request.get("requested", False)
        }
    
    # Step 1: Analyze the request to determine intent and action type
    # Check if request contains order-related items (food, drinks, etc.)
    request_lower = request.lower()
    food_keywords = ["pizza", "margarita", "artichoke", "burger", "food", "drink", "coffee", "restaurant", "delivery"]
    has_food_item = any(keyword in request_lower for keyword in food_keywords)
    
    # If request has food items but no explicit "order", infer it's an order request
    if has_food_item and "order" not in request_lower:
        request = f"order {request}"  # Prepend "order" for better matching
    
    intent_analysis = _analyze_request_intent(request, ai_client)
    action_type = intent_analysis.get("action_type", "message")
    intent = intent_analysis.get("intent", "general")
    
    # Step 2: Match request to contact (exclude user's own phone)
    contact_match = match_contact_to_request(request, ai_client, exclude_phone=user_phone)
    
    if not contact_match:
        # Extract search term from request (e.g., "pizza" from "order pizza")
        search_term = _extract_search_term(request, ai_client)
        
        # No contact found - provide specific error message
        suggestions = get_contact_suggestions(request, limit=3)
        
        # Check if this is a food/drink order
        request_lower = request.lower()
        food_drink_keywords = ["margarita", "artichoke", "pizza", "burger", "food", "drink", "coffee", "restaurant", "bar", "cafe"]
        is_food_order = any(keyword in request_lower for keyword in food_drink_keywords)
        
        # Create specific error message
        if search_term:
            if is_food_order:
                error_message = f"I couldn't find a restaurant or bar contact for '{search_term}' in your contacts. Do you have a restaurant/bar saved in your contacts?"
            else:
                error_message = f"No contact named '{search_term}' or '{search_term} guy' found in your contacts."
        else:
            if is_food_order:
                error_message = f"I couldn't find a restaurant or bar contact for your order in your contacts. Do you have a restaurant/bar saved in your contacts?"
            else:
                error_message = f"I couldn't find a contact for '{request}' in your contact list."
        
        # If we have suggestions, include them
        suggestion_text = ""
        if suggestions:
            suggestion_text = "\n\nHere are some contacts I found:\n"
            for i, sug in enumerate(suggestions[:3], 1):
                suggestion_text += f"{i}. {sug.get('name', 'Unknown')}\n"
            suggestion_text += "\nWould you like me to use one of these?"
        
        return {
            "success": False,
            "action": action_type,
            "message": error_message + suggestion_text,
            "search_term": search_term,
            "suggestions": [
                {
                    "name": c.get("name") or c.get("display_name", "Unknown"),
                    "phone": c.get("phone_number", "")
                }
                for c in suggestions
            ],
            "suggestion_message": "Would you like me to search for contacts matching this request?"
        }
    
    contact = contact_match["contact"]
    confidence = contact_match.get("confidence", 0.5)
    
    # Step 3: Confirm if confidence is low
    if confidence < 0.5:
        contact_name = contact.get("name") or contact.get("display_name", "Unknown")
        return {
            "success": False,
            "action": action_type,
            "message": f"I found '{contact_name}' but I'm not very confident this is the right contact.",
            "contact": contact,  # Return full contact object
            "confidence": confidence,
            "needs_confirmation": True
        }
    
    # Step 4: Execute the action
    result = execute_action(action_type, request, contact, chat_id, ai_client)
    
    # Add context to result
    result["intent"] = intent
    result["confidence"] = confidence
    result["match_reason"] = contact_match.get("match_reason", "")
    
    return result

def _analyze_request_intent(request: str, ai_client: Optional[OpenAI]) -> Dict:
    """Analyze user request to determine action type and intent."""
    
    if not ai_client:
        # Fallback: simple keyword matching
        request_lower = request.lower()
        if any(word in request_lower for word in ["order", "buy", "purchase", "get"]):
            return {"action_type": "order", "intent": "purchase"}
        elif any(word in request_lower for word in ["email", "send email", "mail"]):
            return {"action_type": "email", "intent": "email"}
        elif any(word in request_lower for word in ["call", "phone"]):
            return {"action_type": "call", "intent": "communication"}
        elif any(word in request_lower for word in ["book", "reserve", "reservation"]):
            return {"action_type": "book", "intent": "booking"}
        elif any(word in request_lower for word in ["schedule", "appointment", "meeting"]):
            return {"action_type": "schedule", "intent": "scheduling"}
        else:
            return {"action_type": "message", "intent": "general"}
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Analyze the user's request and determine:
1. Action type: order, email, call, message, book, schedule
2. Intent: what the user wants to accomplish

Return JSON format:
{
  "action_type": "order|email|call|message|book|schedule",
  "intent": "brief description"
}"""},
                {"role": "user", "content": f"User request: {request}"}
            ],
            temperature=0.3,
            max_tokens=100,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"[AgentOrchestrator] Intent analysis error: {e}")
        # Fallback
        request_lower = request.lower()
        if "order" in request_lower or "buy" in request_lower:
            return {"action_type": "order", "intent": "purchase"}
        elif "email" in request_lower or "mail" in request_lower:
            return {"action_type": "email", "intent": "email"}
        elif "call" in request_lower:
            return {"action_type": "call", "intent": "communication"}
        elif "book" in request_lower:
            return {"action_type": "book", "intent": "booking"}
        elif "schedule" in request_lower:
            return {"action_type": "schedule", "intent": "scheduling"}
        else:
            return {"action_type": "message", "intent": "general"}

def _extract_search_term(request: str, ai_client: Optional[OpenAI] = None) -> str:
    """Extract the main search term from a request (e.g., 'pizza' from 'order pizza')."""
    if not ai_client:
        # Simple extraction: remove action words
        action_words = ["order", "buy", "get", "call", "book", "schedule", "find", "contact", "message", "text"]
        words = request.lower().split()
        # Return the first non-action word, or the whole request if all are action words
        for word in words:
            if word not in action_words:
                return word
        return request.split()[0] if request.split() else ""
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Extract the main search term from the user's request.
Examples:
- "order pizza" → "pizza"
- "call my doctor" → "doctor"
- "book a hotel" → "hotel"
- "get me pizza guy" → "pizza"

Return ONLY the search term, nothing else."""},
                {"role": "user", "content": f"Request: {request}\n\nSearch term:"}
            ],
            temperature=0.2,
            max_tokens=20
        )
        return response.choices[0].message.content.strip().lower()
    except Exception as e:
        print(f"[AgentOrchestrator] Search term extraction error: {e}")
        # Fallback: simple extraction
        action_words = ["order", "buy", "get", "call", "book", "schedule", "find", "contact", "message", "text", "my", "a", "the"]
        words = request.lower().split()
        for word in words:
            if word not in action_words:
                return word
        return request.split()[0] if request.split() else ""

def get_action_suggestions(request: str, ai_client: Optional[OpenAI] = None, user_phone: Optional[str] = None) -> List[Dict]:
    """Get suggested actions for a request."""
    intent_analysis = _analyze_request_intent(request, ai_client)
    contact_match = match_contact_to_request(request, ai_client, exclude_phone=user_phone)
    
    suggestions = []
    
    if contact_match:
        contact = contact_match["contact"]
        contact_name = contact.get("name") or contact.get("display_name", "Unknown")
        suggestions.append({
            "action": intent_analysis.get("action_type", "message"),
            "contact": contact_name,
            "description": f"{intent_analysis.get('intent', 'Action')} with {contact_name}",
            "confidence": contact_match.get("confidence", 0.5)
        })
    
    # Add alternative contacts
    alt_contacts = get_contact_suggestions(request, limit=2)
    for contact in alt_contacts:
        if contact.get("name") != contact_match["contact"].get("name") if contact_match else True:
            suggestions.append({
                "action": "message",
                "contact": contact.get("name") or contact.get("display_name", "Unknown"),
                "description": f"Message {contact.get('name', 'Unknown')}",
                "confidence": 0.3
            })
    
    return suggestions

