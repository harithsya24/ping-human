"""Rate limit and quota checking functionality."""
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Rate limit configuration
MAX_MESSAGES_PER_HOUR = int(os.getenv('MAX_MESSAGES_PER_HOUR', 0))  # 0 = no limit
MAX_MESSAGES_PER_DAY = int(os.getenv('MAX_MESSAGES_PER_DAY', 0))  # 0 = no limit

# Track message timestamps
message_timestamps = []

def check_rate_limit() -> tuple[bool, str]:
    """
    Check if we're within rate limits.
    Returns: (can_send, reason_if_not)
    """
    if MAX_MESSAGES_PER_HOUR == 0 and MAX_MESSAGES_PER_DAY == 0:
        return True, ""
    
    now = datetime.now()
    
    # Clean old timestamps (older than 24 hours)
    global message_timestamps
    message_timestamps = [ts for ts in message_timestamps if (now - ts).total_seconds() < 86400]
    
    # Check hourly limit
    if MAX_MESSAGES_PER_HOUR > 0:
        hour_ago = now - timedelta(hours=1)
        recent_messages = [ts for ts in message_timestamps if ts > hour_ago]
        if len(recent_messages) >= MAX_MESSAGES_PER_HOUR:
            return False, f"Hourly limit reached ({MAX_MESSAGES_PER_HOUR} messages/hour)"
    
    # Check daily limit
    if MAX_MESSAGES_PER_DAY > 0:
        day_ago = now - timedelta(days=1)
        daily_messages = [ts for ts in message_timestamps if ts > day_ago]
        if len(daily_messages) >= MAX_MESSAGES_PER_DAY:
            return False, f"Daily limit reached ({MAX_MESSAGES_PER_DAY} messages/day)"
    
    return True, ""

def record_message_sent():
    """Record that a message was sent."""
    message_timestamps.append(datetime.now())

def get_rate_limit_status() -> dict:
    """Get current rate limit status."""
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    
    recent_messages = [ts for ts in message_timestamps if ts > hour_ago]
    daily_messages = [ts for ts in message_timestamps if ts > day_ago]
    
    status = {
        "messages_last_hour": len(recent_messages),
        "messages_last_day": len(daily_messages),
        "hourly_limit": MAX_MESSAGES_PER_HOUR,
        "daily_limit": MAX_MESSAGES_PER_DAY,
        "within_limits": True
    }
    
    if MAX_MESSAGES_PER_HOUR > 0 and len(recent_messages) >= MAX_MESSAGES_PER_HOUR:
        status["within_limits"] = False
        status["limit_reason"] = "hourly"
    elif MAX_MESSAGES_PER_DAY > 0 and len(daily_messages) >= MAX_MESSAGES_PER_DAY:
        status["within_limits"] = False
        status["limit_reason"] = "daily"
    
    return status

