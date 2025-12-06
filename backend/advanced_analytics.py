"""Advanced analytics: peak hours, sentiment trends, response time, engagement."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from analytics import get_analytics
from conversation_tracker import conversation_threads
from action_history import get_action_history
from ai_responder import conversation_history

def get_peak_hours(days: int = 7) -> Dict:
    """Calculate peak active hours over the last N days."""
    hour_counts = defaultdict(int)
    
    for chat_id, messages in conversation_threads.items():
        for msg in messages:
            try:
                timestamp_str = msg.get("timestamp", "")
                if timestamp_str:
                    msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if isinstance(msg_time, datetime):
                        now = datetime.now(msg_time.tzinfo) if msg_time.tzinfo else datetime.now()
                        if (now - msg_time.replace(tzinfo=None) if msg_time.tzinfo else msg_time).days <= days:
                            hour = msg_time.hour
                            hour_counts[hour] += 1
            except:
                continue
    
    peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "peak_hours": [{"hour": h, "count": c} for h, c in peak_hours[:5]],
        "total_messages": sum(hour_counts.values()),
        "hourly_distribution": {h: hour_counts[h] for h in range(24)}
    }

def get_sentiment_trends(days: int = 7) -> Dict:
    """Calculate sentiment trends over time."""
    analytics_data = get_analytics()
    sentiment_counts = analytics_data.get("sentiment_counts", {})
    
    return {
        "current_distribution": sentiment_counts,
        "total": sum(sentiment_counts.values()),
        "positive_ratio": sentiment_counts.get("positive", 0) / max(sum(sentiment_counts.values()), 1),
        "negative_ratio": sentiment_counts.get("negative", 0) / max(sum(sentiment_counts.values()), 1),
        "neutral_ratio": sentiment_counts.get("neutral", 0) / max(sum(sentiment_counts.values()), 1)
    }

def get_response_time_metrics() -> Dict:
    """Calculate average response time metrics."""
    response_times = []
    
    for chat_id, messages in conversation_threads.items():
        user_messages = [m for m in messages if not m.get("is_bot", False)]
        bot_messages = [m for m in messages if m.get("is_bot", False)]
        
        for i, user_msg in enumerate(user_messages):
            try:
                user_time = datetime.fromisoformat(user_msg.get("timestamp", "").replace('Z', '+00:00'))
                if isinstance(user_time, datetime):
                    user_time = user_time.replace(tzinfo=None) if user_time.tzinfo else user_time
                    
                    for bot_msg in bot_messages:
                        bot_time = datetime.fromisoformat(bot_msg.get("timestamp", "").replace('Z', '+00:00'))
                        if isinstance(bot_time, datetime):
                            bot_time = bot_time.replace(tzinfo=None) if bot_time.tzinfo else bot_time
                            
                            if bot_time > user_time:
                                diff_seconds = (bot_time - user_time).total_seconds()
                                if 0 < diff_seconds < 3600:
                                    response_times.append(diff_seconds)
                                    break
            except:
                continue
    
    if not response_times:
        return {
            "average_seconds": 0,
            "median_seconds": 0,
            "min_seconds": 0,
            "max_seconds": 0,
            "total_responses": 0
        }
    
    response_times.sort()
    avg = sum(response_times) / len(response_times)
    median = response_times[len(response_times) // 2]
    
    return {
        "average_seconds": round(avg, 2),
        "median_seconds": round(median, 2),
        "min_seconds": round(min(response_times), 2),
        "max_seconds": round(max(response_times), 2),
        "total_responses": len(response_times),
        "average_minutes": round(avg / 60, 2)
    }

def get_engagement_metrics() -> Dict:
    """Calculate user engagement metrics."""
    analytics_data = get_analytics()
    users = analytics_data.get("users", {})
    
    if not users:
        return {
            "total_users": 0,
            "active_users": 0,
            "average_messages_per_user": 0,
            "most_active_user": None
        }
    
    message_counts = [data.get("message_count", 0) for data in users.values()]
    avg_messages = sum(message_counts) / len(message_counts) if message_counts else 0
    
    most_active = max(users.items(), key=lambda x: x[1].get("message_count", 0))
    
    active_users = len([u for u in users.values() if u.get("message_count", 0) > 0])
    
    return {
        "total_users": len(users),
        "active_users": active_users,
        "average_messages_per_user": round(avg_messages, 2),
        "most_active_user": {
            "phone": most_active[0],
            "message_count": most_active[1].get("message_count", 0),
            "preferred_language": most_active[1].get("preferred_language", "en")
        }
    }

def get_message_volume_metrics(days: int = 7) -> Dict:
    """Calculate message volume metrics."""
    daily_counts = defaultdict(int)
    
    for chat_id, messages in conversation_threads.items():
        for msg in messages:
            try:
                timestamp_str = msg.get("timestamp", "")
                if timestamp_str:
                    msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if isinstance(msg_time, datetime):
                        msg_time = msg_time.replace(tzinfo=None) if msg_time.tzinfo else msg_time
                        now = datetime.now()
                        if (now - msg_time).days <= days:
                            date_key = msg_time.strftime('%Y-%m-%d')
                            daily_counts[date_key] += 1
            except:
                continue
    
    return {
        "daily_volumes": dict(sorted(daily_counts.items())),
        "total_messages": sum(daily_counts.values()),
        "average_per_day": round(sum(daily_counts.values()) / max(days, 1), 2),
        "peak_day": max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None
    }

def get_all_advanced_analytics() -> Dict:
    """Get all advanced analytics in one call."""
    return {
        "peak_hours": get_peak_hours(),
        "sentiment_trends": get_sentiment_trends(),
        "response_time": get_response_time_metrics(),
        "engagement": get_engagement_metrics(),
        "message_volume": get_message_volume_metrics(),
        "generated_at": datetime.now().isoformat()
    }

