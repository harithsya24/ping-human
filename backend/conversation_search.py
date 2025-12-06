"""Conversation search functionality."""
from typing import Dict, List, Optional
from datetime import datetime
from conversation_tracker import get_conversation_thread, get_conversation_summary, conversation_threads
from ai_responder import conversation_history, user_languages
from analytics import get_analytics

def search_conversations(
    query: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    contact: Optional[str] = None,
    sentiment: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """Search conversations by various criteria."""
    results = []
    analytics_data = get_analytics()
    
    for chat_id, messages in conversation_threads.items():
        matches = []
        
        if query:
            query_lower = query.lower()
            for msg in messages:
                if query_lower in msg.get("text", "").lower():
                    matches.append(msg)
        
        if date_from or date_to:
            filtered_messages = []
            for msg in messages:
                try:
                    timestamp_str = msg.get("timestamp", "")
                    if timestamp_str:
                        msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if isinstance(msg_time, datetime):
                            msg_time = msg_time.replace(tzinfo=None) if msg_time.tzinfo else msg_time
                            
                            if date_from:
                                from_date = datetime.fromisoformat(date_from)
                                if msg_time < from_date:
                                    continue
                            
                            if date_to:
                                to_date = datetime.fromisoformat(date_to)
                                if msg_time > to_date:
                                    continue
                            
                            filtered_messages.append(msg)
                except:
                    continue
            
            if not matches:
                matches = filtered_messages
            else:
                matches = [m for m in matches if m in filtered_messages]
        
        if contact:
            contact_lower = contact.lower()
            for msg in messages:
                sender = msg.get("sender", "").lower()
                if contact_lower in sender:
                    if msg not in matches:
                        matches.append(msg)
        
        if sentiment:
            user_data = analytics_data.get("users", {}).get(chat_id, {})
            if sentiment.lower() in str(user_data).lower():
                if not matches:
                    matches = messages[:5]
        
        if matches or (not query and not date_from and not date_to and not contact and not sentiment):
            thread = get_conversation_thread(chat_id)
            summary = get_conversation_summary(chat_id)
            
            result = {
                "chat_id": chat_id,
                "message_count": len(thread),
                "language": user_languages.get(chat_id, "en"),
                "summary": summary,
                "matched_messages": len(matches) if matches else 0,
                "last_message": thread[-1] if thread else None,
                "first_message": thread[0] if thread else None
            }
            
            if query and matches:
                result["matched_messages_list"] = matches[:10]
            
            results.append(result)
    
    results.sort(key=lambda x: x.get("last_message", {}).get("timestamp", ""), reverse=True)
    return results[:limit]

def get_conversation_search_suggestions(query: str) -> List[str]:
    """Get search suggestions based on query."""
    suggestions = []
    query_lower = query.lower()
    
    for chat_id, messages in conversation_threads.items():
        for msg in messages:
            text = msg.get("text", "").lower()
            if query_lower in text:
                words = text.split()
                for i, word in enumerate(words):
                    if query_lower in word:
                        if i > 0:
                            suggestions.append(" ".join(words[max(0, i-2):i+3]))
                        break
    
    return list(set(suggestions))[:10]

