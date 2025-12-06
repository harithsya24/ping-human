"""Decision-making support for conversation management."""
from openai import OpenAI
from typing import Optional, Dict, List
from conversation_tracker import get_conversation_thread, get_conversation_summary, get_pending_replies
from contact_manager import get_contact_name, get_contact_by_phone
from ai_responder import user_languages
from language_detector import get_language_name

def analyze_conversation_state(
    chat_id: str,
    ai_client: Optional[OpenAI] = None
) -> Dict:
    """Analyze conversation state and provide decision support."""
    thread = get_conversation_thread(chat_id, limit=30)
    summary = get_conversation_summary(chat_id)
    
    if not thread:
        return {
            "status": "new_conversation",
            "recommendation": "Send a greeting message",
            "priority": "medium",
            "urgency": "low"
        }
    
    # Analyze last few messages
    recent_messages = thread[-5:]
    last_message = recent_messages[-1] if recent_messages else None
    
    # Check if user is waiting for reply
    pending = get_pending_replies(threshold_minutes=30)
    is_pending = any(p["chat_id"] == chat_id for p in pending)
    
    # Basic analysis
    analysis = {
        "chat_id": chat_id,
        "message_count": summary["message_count"],
        "is_active": summary["active"],
        "is_pending_reply": is_pending,
        "last_activity": summary.get("last_activity"),
        "recommendation": "continue_conversation",
        "priority": "medium",
        "urgency": "low"
    }
    
    if is_pending:
        analysis["recommendation"] = "send_reply"
        analysis["priority"] = "high"
        analysis["urgency"] = "medium"
    
    if not summary["active"]:
        analysis["recommendation"] = "reconnect"
        analysis["priority"] = "low"
        analysis["urgency"] = "low"
    
    return analysis

def get_decision_support(
    chat_id: str,
    question: str,
    context: Optional[Dict] = None,
    ai_client: Optional[OpenAI] = None,
    contact_name: Optional[str] = None
) -> Dict:
    """Get AI-powered decision support for conversation management."""
    if not ai_client:
        return {
            "decision": "continue",
            "reasoning": "AI client not available",
            "suggested_action": "send_generic_message"
        }
    
    thread = get_conversation_thread(chat_id, limit=30)
    summary = get_conversation_summary(chat_id)
    user_lang = user_languages.get(chat_id, "en")
    lang_name = get_language_name(user_lang)
    
    conversation_context = "\n".join([
        f"{'Bot' if msg.get('is_bot') else 'User'}: {msg['text']}"
        for msg in thread[-10:]
    ])
    
    system_prompt = f"""You are a conversation management assistant. Help make decisions about how to handle this conversation.

CONTEXT:
- Contact: {contact_name or 'User'}
- Conversation: {summary['message_count']} messages
- Status: {'Active' if summary['active'] else 'Inactive'}

QUESTION/DECISION NEEDED: {question}

CONVERSATION HISTORY:
{conversation_context if conversation_context else "No previous messages."}

Provide decision support in JSON format:
{{
    "decision": "action_to_take",
    "reasoning": "why this decision",
    "suggested_action": "specific action",
    "priority": "high/medium/low",
    "urgency": "high/medium/low",
    "alternatives": ["option1", "option2"]
}}

Possible decisions:
- send_reply: User is waiting for a response
- wait: Wait for user to respond
- follow_up: Send a follow-up message
- escalate: Escalate to human
- close: End conversation politely"""
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {question}\nProvide decision support."}
            ],
            temperature=0.5,
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        
        import json
        decision_data = json.loads(response.choices[0].message.content)
        return decision_data
    except Exception as e:
        print(f"[DecisionSupport] Error getting decision support: {e}")
        return {
            "decision": "continue",
            "reasoning": f"Error: {str(e)}",
            "suggested_action": "send_generic_message",
            "priority": "medium",
            "urgency": "low"
        }

def should_send_message(
    chat_id: str,
    ai_client: Optional[OpenAI] = None
) -> Dict:
    """Determine if a message should be sent and why."""
    summary = get_conversation_summary(chat_id)
    pending = get_pending_replies(threshold_minutes=60)
    is_pending = any(p["chat_id"] == chat_id for p in pending)
    
    decision = {
        "should_send": False,
        "reason": "",
        "priority": "low",
        "urgency": "low"
    }
    
    if is_pending:
        decision["should_send"] = True
        decision["reason"] = "User sent a message and is waiting for reply"
        decision["priority"] = "high"
        decision["urgency"] = "medium"
    elif not summary["active"]:
        decision["should_send"] = False
        decision["reason"] = "Conversation is inactive (no messages in 24 hours)"
        decision["priority"] = "low"
        decision["urgency"] = "low"
    else:
        decision["should_send"] = False
        decision["reason"] = "No immediate action needed"
        decision["priority"] = "medium"
        decision["urgency"] = "low"
    
    return decision

def get_conversation_insights(
    chat_id: str,
    ai_client: Optional[OpenAI] = None
) -> Dict:
    """Get insights about a conversation for better decision-making."""
    thread = get_conversation_thread(chat_id, limit=50)
    summary = get_conversation_summary(chat_id)
    
    if not thread:
        return {
            "insights": [],
            "topics": [],
            "sentiment_trend": "neutral",
            "engagement_level": "low"
        }
    
    # Analyze conversation
    user_messages = [msg for msg in thread if not msg.get("is_bot", False)]
    bot_messages = [msg for msg in thread if msg.get("is_bot", False)]
    
    insights = {
        "message_count": len(thread),
        "user_messages": len(user_messages),
        "bot_messages": len(bot_messages),
        "engagement_level": "high" if len(thread) > 10 else "medium" if len(thread) > 5 else "low",
        "response_rate": len(bot_messages) / len(user_messages) if user_messages else 0,
        "is_active": summary["active"],
        "last_activity": summary.get("last_activity")
    }
    
    return insights

