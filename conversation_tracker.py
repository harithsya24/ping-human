"""Conversation tracking and reply detection."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

# Conversation threads: chat_id -> list of messages with metadata
conversation_threads: Dict[str, List[dict]] = {}

# Reply detection: track last message from each sender per chat
last_messages: Dict[str, dict] = {}  # chat_id -> {sender, timestamp, text}

# Message timestamps for reply detection
message_timestamps: Dict[str, List[datetime]] = defaultdict(list)

def add_message(chat_id: str, sender: str, text: str, message_id: Optional[str] = None, is_bot: bool = False):
    """Add a message to conversation thread."""
    if chat_id not in conversation_threads:
        conversation_threads[chat_id] = []
    
    message_entry = {
        "sender": sender,
        "text": text,
        "timestamp": datetime.now().isoformat(),
        "message_id": message_id,
        "is_bot": is_bot
    }
    
    conversation_threads[chat_id].append(message_entry)
    message_timestamps[chat_id].append(datetime.now())
    
    # Track last message from this sender
    if not is_bot:
        last_messages[chat_id] = {
            "sender": sender,
            "text": text,
            "timestamp": datetime.now(),
            "message_id": message_id
        }
    
    # Keep only last 200 messages per chat
    if len(conversation_threads[chat_id]) > 200:
        conversation_threads[chat_id] = conversation_threads[chat_id][-200:]
        message_timestamps[chat_id] = message_timestamps[chat_id][-200:]

def has_replied(chat_id: str, sender: str, within_minutes: int = 60) -> bool:
    """Check if a person has replied within the specified time window."""
    if chat_id not in last_messages:
        return False
    
    last_msg = last_messages[chat_id]
    if last_msg["sender"] != sender:
        return False
    
    time_diff = datetime.now() - last_msg["timestamp"]
    return time_diff.total_seconds() / 60 <= within_minutes

def get_conversation_thread(chat_id: str, limit: int = 50) -> List[dict]:
    """Get conversation thread for a chat."""
    if chat_id not in conversation_threads:
        return []
    return conversation_threads[chat_id][-limit:]

def get_last_message_from(chat_id: str, sender: str) -> Optional[dict]:
    """Get the last message from a specific sender in a chat."""
    if chat_id not in conversation_threads:
        return None
    
    for msg in reversed(conversation_threads[chat_id]):
        if msg["sender"] == sender and not msg.get("is_bot", False):
            return msg
    return None

def get_conversation_summary(chat_id: str) -> dict:
    """Get summary statistics for a conversation."""
    if chat_id not in conversation_threads:
        return {
            "chat_id": chat_id,
            "message_count": 0,
            "participants": [],
            "last_activity": None,
            "active": False
        }
    
    messages = conversation_threads[chat_id]
    participants = list(set(msg["sender"] for msg in messages))
    last_activity = messages[-1]["timestamp"] if messages else None
    
    # Check if conversation is active (message in last 24 hours)
    is_active = False
    if last_activity:
        last_time = datetime.fromisoformat(last_activity)
        is_active = (datetime.now() - last_time).total_seconds() < 86400
    
    return {
        "chat_id": chat_id,
        "message_count": len(messages),
        "participants": participants,
        "last_activity": last_activity,
        "active": is_active,
        "bot_messages": sum(1 for msg in messages if msg.get("is_bot", False)),
        "user_messages": sum(1 for msg in messages if not msg.get("is_bot", False))
    }

def get_all_threads() -> Dict[str, List[dict]]:
    """Get all conversation threads."""
    return conversation_threads.copy()

def get_pending_replies(threshold_minutes: int = 60) -> List[dict]:
    """Get conversations that need replies (user sent message but no bot reply recently)."""
    pending = []
    for chat_id, messages in conversation_threads.items():
        if not messages:
            continue
        
        # Get last user message
        last_user_msg = None
        last_bot_msg = None
        
        for msg in reversed(messages):
            if not msg.get("is_bot", False) and not last_user_msg:
                last_user_msg = msg
            if msg.get("is_bot", False) and not last_bot_msg:
                last_bot_msg = msg
            if last_user_msg and last_bot_msg:
                break
        
        if last_user_msg and not last_bot_msg:
            # User sent message but bot never replied
            pending.append({
                "chat_id": chat_id,
                "last_user_message": last_user_msg,
                "time_since_message": (datetime.now() - datetime.fromisoformat(last_user_msg["timestamp"])).total_seconds() / 60
            })
        elif last_user_msg and last_bot_msg:
            # Check if user replied after bot's last message
            user_time = datetime.fromisoformat(last_user_msg["timestamp"])
            bot_time = datetime.fromisoformat(last_bot_msg["timestamp"])
            if user_time > bot_time:
                minutes_since = (datetime.now() - user_time).total_seconds() / 60
                if minutes_since > threshold_minutes:
                    pending.append({
                        "chat_id": chat_id,
                        "last_user_message": last_user_msg,
                        "last_bot_message": last_bot_msg,
                        "time_since_message": minutes_since
                    })
    
    return sorted(pending, key=lambda x: x["time_since_message"], reverse=True)

