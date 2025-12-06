"""Memory-accurate conversation history retrieval system."""
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from conversation_tracker import conversation_threads, get_conversation_thread
from ai_responder import conversation_history
from messaging_rules import get_non_hallucination_response, validate_json_context, validate_message_storage

MEMORY_RETRIEVAL_KEYWORDS = [
    "what did i say", "what did we talk", "show me my past", "show me past messages",
    "what was the conversation", "conversation with id", "what did i say on",
    "what did i say that day", "what did we discuss", "my messages on",
    "conversation history", "past conversation", "previous messages",
    "what did i tell", "what did i mention", "remember when", "recall"
]

def is_memory_retrieval_request(text: str) -> bool:
    """Check if the request is asking for memory retrieval."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in MEMORY_RETRIEVAL_KEYWORDS)

def get_conversation_by_id(chat_id: str) -> Optional[Dict]:
    """Get conversation by chat ID from stored history."""
    if chat_id in conversation_threads:
        thread = conversation_threads[chat_id]
        return {
            "chat_id": chat_id,
            "messages": thread,
            "message_count": len(thread),
            "found": True
        }
    return None

def search_conversations_by_date(date_str: str) -> List[Dict]:
    """Search conversations by date. Returns exact matches only."""
    results = []
    
    try:
        target_date = _parse_date(date_str)
        if not target_date:
            return []
        
        for chat_id, thread in conversation_threads.items():
            matching_messages = []
            for msg in thread:
                msg_timestamp = msg.get("timestamp")
                if msg_timestamp:
                    msg_date = _parse_timestamp_to_date(msg_timestamp)
                    if msg_date and msg_date.date() == target_date.date():
                        matching_messages.append(msg)
            
            if matching_messages:
                results.append({
                    "chat_id": chat_id,
                    "date": target_date.isoformat(),
                    "messages": matching_messages,
                    "count": len(matching_messages)
                })
    except Exception as e:
        print(f"[MemoryRetrieval] Error searching by date: {e}")
    
    return results

def search_conversations_by_date_range(start_date: str, end_date: str) -> List[Dict]:
    """Search conversations within a date range. Returns exact matches only."""
    results = []
    
    try:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        
        if not start or not end:
            return []
        
        for chat_id, thread in conversation_threads.items():
            matching_messages = []
            for msg in thread:
                msg_timestamp = msg.get("timestamp")
                if msg_timestamp:
                    msg_date = _parse_timestamp_to_date(msg_timestamp)
                    if msg_date and start.date() <= msg_date.date() <= end.date():
                        matching_messages.append(msg)
            
            if matching_messages:
                results.append({
                    "chat_id": chat_id,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "messages": matching_messages,
                    "count": len(matching_messages)
                })
    except Exception as e:
        print(f"[MemoryRetrieval] Error searching by date range: {e}")
    
    return results

def get_user_messages_only(chat_id: Optional[str] = None, date: Optional[str] = None) -> List[Dict]:
    """Get only user messages (not bot responses). Returns exact matches only."""
    results = []
    
    try:
        if chat_id:
            if chat_id in conversation_threads:
                thread = conversation_threads[chat_id]
                user_messages = [msg for msg in thread if not msg.get("is_bot", False)]
                
                if date:
                    target_date = _parse_date(date)
                    if target_date:
                        user_messages = [
                            msg for msg in user_messages
                            if _parse_timestamp_to_date(msg.get("timestamp", "")) and
                            _parse_timestamp_to_date(msg.get("timestamp", "")).date() == target_date.date()
                        ]
                
                results = user_messages
        else:
            for thread in conversation_threads.values():
                user_messages = [msg for msg in thread if not msg.get("is_bot", False)]
                if date:
                    target_date = _parse_date(date)
                    if target_date:
                        user_messages = [
                            msg for msg in user_messages
                            if _parse_timestamp_to_date(msg.get("timestamp", "")) and
                            _parse_timestamp_to_date(msg.get("timestamp", "")).date() == target_date.date()
                        ]
                results.extend(user_messages)
    except Exception as e:
        print(f"[MemoryRetrieval] Error getting user messages: {e}")
    
    return results

def search_by_keyword(keyword: str, chat_id: Optional[str] = None) -> List[Dict]:
    """Search messages by keyword. Returns exact matches only."""
    results = []
    keyword_lower = keyword.lower()
    
    try:
        if chat_id:
            if chat_id in conversation_threads:
                thread = conversation_threads[chat_id]
                matching = [
                    msg for msg in thread
                    if keyword_lower in msg.get("text", "").lower()
                ]
                if matching:
                    results.append({
                        "chat_id": chat_id,
                        "keyword": keyword,
                        "messages": matching,
                        "count": len(matching)
                    })
        else:
            for cid, thread in conversation_threads.items():
                matching = [
                    msg for msg in thread
                    if keyword_lower in msg.get("text", "").lower()
                ]
                if matching:
                    results.append({
                        "chat_id": cid,
                        "keyword": keyword,
                        "messages": matching,
                        "count": len(matching)
                    })
    except Exception as e:
        print(f"[MemoryRetrieval] Error searching by keyword: {e}")
    
    return results

def format_memory_response(results: List[Dict], query_type: str) -> str:
    """Format memory retrieval results into a response. Only uses exact data from JSON logs. STRICT: No hallucination."""
    if not results:
        return get_non_hallucination_response()
    
    for result in results:
        if not validate_json_context(result):
            return get_non_hallucination_response()
    
    response_parts = []
    
    if query_type == "conversation_id":
        for result in results:
            chat_id = result.get("chat_id", "Unknown")
            messages = result.get("messages", [])
            response_parts.append(f"📋 Conversation {chat_id} ({len(messages)} messages):")
            for msg in messages[:10]:
                sender = msg.get("sender", "Unknown")
                text = msg.get("text", "")
                timestamp = msg.get("timestamp", "")
                is_bot = msg.get("is_bot", False)
                role = "Bot" if is_bot else "You"
                response_parts.append(f"  {role}: {text}")
            if len(messages) > 10:
                response_parts.append(f"  ... and {len(messages) - 10} more messages")
    
    elif query_type == "date":
        for result in results:
            chat_id = result.get("chat_id", "Unknown")
            date = result.get("date", "Unknown")
            messages = result.get("messages", [])
            response_parts.append(f" On {date} in conversation {chat_id} ({len(messages)} messages):")
            for msg in messages[:5]:
                text = msg.get("text", "")
                is_bot = msg.get("is_bot", False)
                role = "Bot" if is_bot else "You"
                response_parts.append(f"  {role}: {text[:100]}")
            if len(messages) > 5:
                response_parts.append(f"  ... and {len(messages) - 5} more messages")
    
    elif query_type == "user_messages":
        response_parts.append(f" Your messages ({len(results)} found):")
        for msg in results[:10]:
            text = msg.get("text", "")
            timestamp = msg.get("timestamp", "")
            response_parts.append(f"  • {text}")
        if len(results) > 10:
            response_parts.append(f"  ... and {len(results) - 10} more messages")
    
    elif query_type == "keyword":
        for result in results:
            chat_id = result.get("chat_id", "Unknown")
            keyword = result.get("keyword", "")
            messages = result.get("messages", [])
            response_parts.append(f" Found '{keyword}' in conversation {chat_id} ({len(messages)} matches):")
            for msg in messages[:5]:
                text = msg.get("text", "")
                is_bot = msg.get("is_bot", False)
                role = "Bot" if is_bot else "You"
                response_parts.append(f"  {role}: {text[:150]}")
            if len(messages) > 5:
                response_parts.append(f"  ... and {len(messages) - 5} more matches")
    
    return "\n".join(response_parts) if response_parts else get_non_hallucination_response()

def process_memory_request(text: str, chat_id: str) -> Optional[str]:
    """Process a memory retrieval request. Returns exact matches only."""
    text_lower = text.lower()
    
    if "conversation with id" in text_lower or "conversation id" in text_lower:
        import re
        id_match = re.search(r'id\s+(\w+)', text_lower)
        if id_match:
            conv_id = id_match.group(1)
            result = get_conversation_by_id(conv_id)
            if result:
                return format_memory_response([result], "conversation_id")
            return get_non_hallucination_response()
    
    if "what did i say on" in text_lower or "my messages on" in text_lower:
        import re
        date_match = re.search(r'on\s+([\d\-/]+)', text_lower)
        if date_match:
            date_str = date_match.group(1)
            results = search_conversations_by_date(date_str)
            if results:
                return format_memory_response(results, "date")
            return get_non_hallucination_response()
    
    if "what did i say" in text_lower and "that day" in text_lower:
        import re
        date_match = re.search(r'that day[,\s]+([\d\-/]+)', text_lower)
        if date_match:
            date_str = date_match.group(1)
            results = get_user_messages_only(chat_id=chat_id, date=date_str)
            if results:
                return format_memory_response(results, "user_messages")
            return get_non_hallucination_response()
    
    if "show me my past messages" in text_lower or "my past messages" in text_lower:
        results = get_user_messages_only(chat_id=chat_id)
        if results:
            return format_memory_response(results, "user_messages")
        return get_non_hallucination_response()
    
    if "what did we talk about" in text_lower or "what did we discuss" in text_lower:
        if "last week" in text_lower:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            results = search_conversations_by_date_range(start_date.isoformat(), end_date.isoformat())
            if results:
                return format_memory_response(results, "date")
            return get_non_hallucination_response()
    
    return None

def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime. Returns None if cannot parse."""
    if not date_str:
        return None
    
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m-%d-%Y",
        "%d-%m-%Y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    
    return None

def _parse_timestamp_to_date(timestamp_str: str) -> Optional[datetime]:
    """Parse timestamp string to datetime. Returns None if cannot parse."""
    if not timestamp_str:
        return None
    
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        return None

