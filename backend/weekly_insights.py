"""Weekly insights report generator."""
from typing import Dict
from datetime import datetime, timedelta
from analytics import get_analytics
from advanced_analytics import get_all_advanced_analytics
from action_history import get_action_history
from conversation_tracker import conversation_threads

def generate_weekly_report() -> Dict:
    """Generate weekly insights report."""
    analytics_data = get_analytics()
    advanced_analytics = get_all_advanced_analytics()
    action_history = get_action_history(limit=1000)
    
    week_ago = datetime.now() - timedelta(days=7)
    recent_actions = [
        a for a in action_history
        if _parse_timestamp(a.get("timestamp", "")) >= week_ago
    ]
    
    total_messages = analytics_data.get("total_messages", 0)
    total_responses = analytics_data.get("total_responses", 0)
    unique_users = len(analytics_data.get("users", {}))
    
    sentiment_dist = analytics_data.get("sentiment_counts", {})
    top_languages = dict(sorted(
        analytics_data.get("language_counts", {}).items(),
        key=lambda x: x[1],
        reverse=True
    )[:5])
    
    peak_hours = advanced_analytics.get("peak_hours", {}).get("peak_hours", [])
    response_time = advanced_analytics.get("response_time", {})
    engagement = advanced_analytics.get("engagement", {})
    
    successful_actions = sum(1 for a in recent_actions if a.get("details", {}).get("success") is True)
    failed_actions = sum(1 for a in recent_actions if a.get("details", {}).get("success") is False)
    
    top_actions = {}
    for action in recent_actions:
        action_type = action.get("action_type", "unknown")
        top_actions[action_type] = top_actions.get(action_type, 0) + 1
    
    top_actions_sorted = dict(sorted(top_actions.items(), key=lambda x: x[1], reverse=True)[:5])
    
    active_conversations = len([c for c in conversation_threads.values() if len(c) > 0])
    
    return {
        "period": "Last 7 days",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_messages": total_messages,
            "total_responses": total_responses,
            "response_rate": round((total_responses / max(total_messages, 1)) * 100, 2),
            "unique_users": unique_users,
            "active_conversations": active_conversations
        },
        "sentiment_analysis": {
            "distribution": sentiment_dist,
            "positive_ratio": round(sentiment_dist.get("positive", 0) / max(sum(sentiment_dist.values()), 1) * 100, 2),
            "negative_ratio": round(sentiment_dist.get("negative", 0) / max(sum(sentiment_dist.values()), 1) * 100, 2)
        },
        "language_diversity": {
            "top_languages": top_languages,
            "total_languages": len(analytics_data.get("language_counts", {}))
        },
        "performance": {
            "peak_hours": [{"hour": h["hour"], "count": h["count"]} for h in peak_hours[:3]],
            "average_response_time_seconds": response_time.get("average_seconds", 0),
            "average_response_time_minutes": response_time.get("average_minutes", 0)
        },
        "engagement": {
            "most_active_user": engagement.get("most_active_user"),
            "average_messages_per_user": engagement.get("average_messages_per_user", 0)
        },
        "actions": {
            "total_actions": len(recent_actions),
            "successful": successful_actions,
            "failed": failed_actions,
            "success_rate": round((successful_actions / max(len(recent_actions), 1)) * 100, 2),
            "top_action_types": top_actions_sorted
        },
        "insights": _generate_insights(
            total_messages, sentiment_dist, peak_hours, response_time,
            successful_actions, failed_actions
        )
    }

def _parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string to datetime."""
    try:
        if not timestamp_str:
            return datetime.min
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        return datetime.min

def _generate_insights(
    total_messages: int,
    sentiment_dist: Dict,
    peak_hours: list,
    response_time: Dict,
    successful_actions: int,
    failed_actions: int
) -> list[str]:
    """Generate human-readable insights."""
    insights = []
    
    if total_messages > 100:
        insights.append(f"High activity: {total_messages} messages processed this week")
    
    positive_ratio = sentiment_dist.get("positive", 0) / max(sum(sentiment_dist.values()), 1)
    if positive_ratio > 0.6:
        insights.append("Positive sentiment is high - users are satisfied")
    elif positive_ratio < 0.3:
        insights.append("Consider reviewing negative feedback patterns")
    
    if peak_hours:
        peak_hour = peak_hours[0]
        insights.append(f"Peak activity at {peak_hour['hour']}:00 with {peak_hour['count']} messages")
    
    avg_response = response_time.get("average_seconds", 0)
    if avg_response < 5:
        insights.append("Excellent response time - under 5 seconds average")
    elif avg_response > 30:
        insights.append("Response time could be improved - currently over 30 seconds")
    
    if successful_actions > failed_actions * 5:
        insights.append("High action success rate - system performing well")
    elif failed_actions > successful_actions:
        insights.append("Action failure rate is high - review error patterns")
    
    return insights

