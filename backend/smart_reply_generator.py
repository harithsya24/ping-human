"""Smart reply suggestions generator (UI only, no auto-sending)."""
from typing import List, Dict, Optional
from openai import OpenAI
from conversation_tracker import get_conversation_thread
from ai_responder import conversation_history

def generate_smart_replies(
    chat_id: str,
    last_message: str,
    ai_client: Optional[OpenAI] = None,
    num_suggestions: int = 4
) -> List[Dict]:
    """Generate smart reply suggestions for a conversation."""
    if not ai_client:
        return _get_fallback_replies(last_message, num_suggestions)
    
    try:
        thread = get_conversation_thread(chat_id, limit=10)
        
        context = "\n".join([
            f"{'Bot' if msg.get('is_bot') else 'User'}: {msg.get('text', '')}"
            for msg in thread[-5:]
        ])
        
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""Generate {num_suggestions} short, natural reply suggestions for the user's last message.
Each suggestion should be:
- Brief (1-2 sentences max)
- Contextually appropriate
- Varied in tone and approach
- Professional but friendly

Return as JSON array of strings."""
                },
                {
                    "role": "user",
                    "content": f"Conversation context:\n{context}\n\nLast message: {last_message}\n\nGenerate {num_suggestions} reply suggestions:"
                }
            ],
            temperature=0.8,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        suggestions = result.get("suggestions", result.get("replies", []))
        
        if isinstance(suggestions, list) and len(suggestions) >= num_suggestions:
            return [
                {"text": s, "confidence": 0.8 - (i * 0.1), "type": "ai_generated"}
                for i, s in enumerate(suggestions[:num_suggestions])
            ]
        else:
            return _get_fallback_replies(last_message, num_suggestions)
    
    except Exception as e:
        print(f"[SmartReply] Error generating suggestions: {e}")
        return _get_fallback_replies(last_message, num_suggestions)

def _get_fallback_replies(message: str, num: int) -> List[Dict]:
    """Get fallback reply suggestions."""
    message_lower = message.lower()
    
    suggestions = []
    
    if any(word in message_lower for word in ["thanks", "thank", "appreciate"]):
        suggestions = [
            {"text": "You're welcome!", "confidence": 0.9, "type": "template"},
            {"text": "Happy to help!", "confidence": 0.8, "type": "template"},
            {"text": "Anytime!", "confidence": 0.7, "type": "template"},
            {"text": "Glad I could assist!", "confidence": 0.6, "type": "template"}
        ]
    elif any(word in message_lower for word in ["hello", "hi", "hey"]):
        suggestions = [
            {"text": "Hello! How can I help you today?", "confidence": 0.9, "type": "template"},
            {"text": "Hi there! What can I do for you?", "confidence": 0.8, "type": "template"},
            {"text": "Hey! What's up?", "confidence": 0.7, "type": "template"},
            {"text": "Hi! How are you?", "confidence": 0.6, "type": "template"}
        ]
    elif "?" in message:
        suggestions = [
            {"text": "Let me check that for you.", "confidence": 0.8, "type": "template"},
            {"text": "I can help with that!", "confidence": 0.7, "type": "template"},
            {"text": "Good question! Let me find out.", "confidence": 0.6, "type": "template"},
            {"text": "I'll look into that.", "confidence": 0.5, "type": "template"}
        ]
    else:
        suggestions = [
            {"text": "Got it!", "confidence": 0.7, "type": "template"},
            {"text": "Understood.", "confidence": 0.6, "type": "template"},
            {"text": "Okay, I'll handle that.", "confidence": 0.5, "type": "template"},
            {"text": "Sounds good!", "confidence": 0.4, "type": "template"}
        ]
    
    return suggestions[:num]

