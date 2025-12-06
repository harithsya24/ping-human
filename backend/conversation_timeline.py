"""Conversation timeline visualization data."""
from typing import Dict, List
from datetime import datetime
from conversation_tracker import get_conversation_thread, conversation_threads
from ai_responder import conversation_history, user_languages

def get_conversation_timeline(chat_id: str) -> Dict:
    """Get timeline data for a conversation."""
    thread = get_conversation_thread(chat_id)
    
    timeline_events = []
    
    for msg in thread:
        try:
            timestamp_str = msg.get("timestamp", "")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if timestamp.tzinfo:
                    timestamp = timestamp.replace(tzinfo=None)
            else:
                timestamp = datetime.now()
            
            event = {
                "id": msg.get("message_id", f"msg_{len(timeline_events)}"),
                "timestamp": timestamp.isoformat(),
                "type": "bot_message" if msg.get("is_bot") else "user_message",
                "sender": msg.get("sender", "Unknown"),
                "text": msg.get("text", ""),
                "is_bot": msg.get("is_bot", False)
            }
            
            timeline_events.append(event)
        except:
            continue
    
    timeline_events.sort(key=lambda x: x.get("timestamp", ""))
    
    return {
        "chat_id": chat_id,
        "language": user_languages.get(chat_id, "en"),
        "total_messages": len(timeline_events),
        "events": timeline_events,
        "start_time": timeline_events[0].get("timestamp") if timeline_events else None,
        "end_time": timeline_events[-1].get("timestamp") if timeline_events else None,
        "duration_seconds": _calculate_duration(timeline_events)
    }

def get_all_timelines() -> Dict[str, Dict]:
    """Get timelines for all conversations."""
    timelines = {}
    
    for chat_id in conversation_threads.keys():
        timelines[chat_id] = get_conversation_timeline(chat_id)
    
    return timelines

def get_timeline_summary(chat_id: str) -> Dict:
    """Get summary statistics for timeline."""
    timeline = get_conversation_timeline(chat_id)
    events = timeline.get("events", [])
    
    if not events:
        return {
            "chat_id": chat_id,
            "message_count": 0,
            "user_messages": 0,
            "bot_messages": 0,
            "average_response_time": 0
        }
    
    user_messages = [e for e in events if not e.get("is_bot")]
    bot_messages = [e for e in events if e.get("is_bot")]
    
    response_times = []
    for i, user_msg in enumerate(user_messages):
        user_time = _parse_timestamp(user_msg.get("timestamp", ""))
        if user_time:
            for bot_msg in bot_messages:
                bot_time = _parse_timestamp(bot_msg.get("timestamp", ""))
                if bot_time and bot_time > user_time:
                    response_times.append((bot_time - user_time).total_seconds())
                    break
    
    avg_response = sum(response_times) / len(response_times) if response_times else 0
    
    return {
        "chat_id": chat_id,
        "message_count": len(events),
        "user_messages": len(user_messages),
        "bot_messages": len(bot_messages),
        "average_response_time_seconds": round(avg_response, 2),
        "duration_seconds": timeline.get("duration_seconds", 0)
    }

def _parse_timestamp(timestamp_str: str):
    """Parse timestamp string."""
    try:
        if not timestamp_str:
            return None
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        return None

def _calculate_duration(events: List[Dict]) -> float:
    """Calculate conversation duration in seconds."""
    if len(events) < 2:
        return 0.0
    
    try:
        start = _parse_timestamp(events[0].get("timestamp", ""))
        end = _parse_timestamp(events[-1].get("timestamp", ""))
        
        if start and end:
            return (end - start).total_seconds()
    except:
        pass
    
    return 0.0

def get_timeline_visualization_data(chat_id: str) -> Dict:
    """Get data formatted for timeline visualization."""
    timeline = get_conversation_timeline(chat_id)
    events = timeline.get("events", [])
    
    visualization_data = {
        "chat_id": chat_id,
        "timeline": []
    }
    
    for event in events:
        timestamp = _parse_timestamp(event.get("timestamp", ""))
        if timestamp:
            visualization_data["timeline"].append({
                "time": timestamp.isoformat(),
                "type": event.get("type"),
                "sender": event.get("sender"),
                "message": event.get("text", "")[:100],
                "is_bot": event.get("is_bot", False)
            })
    
    return visualization_data

