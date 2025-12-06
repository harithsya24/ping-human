"""System health and performance metrics."""
from typing import Dict, List
from datetime import datetime, timedelta
from action_history import get_action_history
from rate_limit_checker import get_rate_limit_status
from guardrails import get_guardrail_stats
from analytics import get_analytics

def get_system_health() -> Dict:
    """Get comprehensive system health metrics."""
    try:
        action_history = get_action_history(limit=1000)
        rate_limit_status = get_rate_limit_status()
        guardrail_stats = get_guardrail_stats()
        analytics_data = get_analytics()
        
        error_count = sum(1 for action in action_history if action.get("action_type") == "error")
        failed_actions = sum(1 for action in action_history if action.get("details", {}).get("success") is False)
        
        recent_actions = [a for a in action_history if _is_recent(a.get("timestamp", ""), hours=24)]
        recent_errors = sum(1 for a in recent_actions if a.get("action_type") == "error")
        
        total_actions = len(action_history)
        success_rate = ((total_actions - failed_actions) / max(total_actions, 1)) * 100
        
        return {
            "status": "healthy" if recent_errors < 10 and success_rate > 80 else "degraded" if recent_errors < 50 else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "total_actions": total_actions,
                "error_count": error_count,
                "recent_errors_24h": recent_errors,
                "failed_actions": failed_actions,
                "success_rate": round(success_rate, 2),
                "rate_limit_status": rate_limit_status,
                "guardrail_stats": guardrail_stats,
                "total_messages": analytics_data.get("total_messages", 0),
                "total_responses": analytics_data.get("total_responses", 0)
            },
            "health_score": _calculate_health_score(recent_errors, success_rate, rate_limit_status)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def _is_recent(timestamp_str: str, hours: int = 24) -> bool:
    """Check if timestamp is within last N hours."""
    try:
        if not timestamp_str:
            return False
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=None)
        now = datetime.now()
        return (now - timestamp).total_seconds() < (hours * 3600)
    except:
        return False

def _calculate_health_score(recent_errors: int, success_rate: float, rate_limit_status: Dict) -> float:
    """Calculate overall health score (0-100)."""
    error_score = max(0, 100 - (recent_errors * 2))
    success_score = success_rate
    rate_limit_penalty = 10 if rate_limit_status.get("rate_limited", False) else 0
    
    return max(0, min(100, (error_score + success_score) / 2 - rate_limit_penalty))

def get_latency_metrics() -> Dict:
    """Get latency metrics from action history."""
    action_history = get_action_history(limit=1000)
    
    latencies = []
    for action in action_history:
        details = action.get("details", {})
        if "latency_ms" in details:
            latencies.append(details["latency_ms"])
    
    if not latencies:
        return {
            "average_ms": 0,
            "median_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "count": 0
        }
    
    latencies.sort()
    avg = sum(latencies) / len(latencies)
    median = latencies[len(latencies) // 2]
    p95_idx = int(len(latencies) * 0.95)
    p99_idx = int(len(latencies) * 0.99)
    
    return {
        "average_ms": round(avg, 2),
        "median_ms": round(median, 2),
        "p95_ms": round(latencies[min(p95_idx, len(latencies) - 1)], 2),
        "p99_ms": round(latencies[min(p99_idx, len(latencies) - 1)], 2),
        "count": len(latencies)
    }

def get_error_breakdown() -> Dict:
    """Get breakdown of errors by type."""
    action_history = get_action_history(limit=1000)
    error_actions = [a for a in action_history if a.get("action_type") == "error"]
    
    error_types = {}
    for action in error_actions:
        error_type = action.get("details", {}).get("error_type", "unknown")
        error_types[error_type] = error_types.get(error_type, 0) + 1
    
    return {
        "total_errors": len(error_actions),
        "error_types": error_types,
        "recent_errors_24h": sum(1 for a in error_actions if _is_recent(a.get("timestamp", ""), hours=24))
    }

def get_rate_limit_metrics() -> Dict:
    """Get rate limit metrics."""
    rate_limit_status = get_rate_limit_status()
    
    return {
        "rate_limited": rate_limit_status.get("rate_limited", False),
        "messages_sent_today": rate_limit_status.get("messages_sent_today", 0),
        "messages_sent_hour": rate_limit_status.get("messages_sent_hour", 0),
        "quota_remaining": rate_limit_status.get("quota_remaining", "unknown"),
        "reset_time": rate_limit_status.get("reset_time")
    }

def get_failed_actions_summary() -> Dict:
    """Get summary of failed actions."""
    action_history = get_action_history(limit=1000)
    failed = [a for a in action_history if a.get("details", {}).get("success") is False]
    
    failed_by_type = {}
    for action in failed:
        action_type = action.get("action_type", "unknown")
        failed_by_type[action_type] = failed_by_type.get(action_type, 0) + 1
    
    return {
        "total_failed": len(failed),
        "failed_by_type": failed_by_type,
        "recent_failures_24h": sum(1 for a in failed if _is_recent(a.get("timestamp", ""), hours=24))
    }

