"""Smart notification system for dashboard alerts (internal only, no SMS)."""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from threading import Lock
from action_history import get_action_history
from system_health import get_system_health
from analytics import get_analytics

NOTIFICATIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notifications.json")
_notifications_lock = Lock()

def _load_notifications() -> List[Dict]:
    """Load notifications from file."""
    if os.path.exists(NOTIFICATIONS_FILE):
        try:
            with open(NOTIFICATIONS_FILE, 'r') as f:
                data = json.load(f)
                return data.get("notifications", [])
        except:
            return []
    return []

def _save_notifications(notifications: List[Dict]):
    """Save notifications to file."""
    try:
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump({"notifications": notifications}, f, indent=2)
    except Exception as e:
        print(f"[Notifications] Error saving: {e}")

def create_notification(
    title: str,
    message: str,
    type: str = "info",
    priority: str = "normal",
    category: Optional[str] = None,
    action_url: Optional[str] = None,
    expires_in_hours: Optional[int] = None
) -> Dict:
    """Create a new notification."""
    with _notifications_lock:
        notifications = _load_notifications()
        
        notification = {
            "id": f"notif_{len(notifications) + 1}_{int(datetime.now().timestamp())}",
            "title": title,
            "message": message,
            "type": type,
            "priority": priority,
            "category": category,
            "action_url": action_url,
            "read": False,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=expires_in_hours)).isoformat() if expires_in_hours else None
        }
        
        notifications.append(notification)
        _save_notifications(notifications)
        
        return notification

def get_notifications(unread_only: bool = False, limit: int = 50) -> List[Dict]:
    """Get notifications, optionally filtered by read status."""
    notifications = _load_notifications()
    
    now = datetime.now()
    active_notifications = []
    
    for notif in notifications:
        expires_at = notif.get("expires_at")
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at)
                if exp_time < now:
                    continue
            except:
                pass
        
        if unread_only and notif.get("read", False):
            continue
        
        active_notifications.append(notif)
    
    active_notifications.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return active_notifications[:limit]

def mark_notification_read(notification_id: str) -> bool:
    """Mark a notification as read."""
    with _notifications_lock:
        notifications = _load_notifications()
        
        for notif in notifications:
            if notif.get("id") == notification_id:
                notif["read"] = True
                notif["read_at"] = datetime.now().isoformat()
                _save_notifications(notifications)
                return True
        
        return False

def mark_all_read() -> int:
    """Mark all notifications as read."""
    with _notifications_lock:
        notifications = _load_notifications()
        count = 0
        
        for notif in notifications:
            if not notif.get("read", False):
                notif["read"] = True
                notif["read_at"] = datetime.now().isoformat()
                count += 1
        
        _save_notifications(notifications)
        return count

def delete_notification(notification_id: str) -> bool:
    """Delete a notification."""
    with _notifications_lock:
        notifications = _load_notifications()
        original_count = len(notifications)
        
        notifications = [n for n in notifications if n.get("id") != notification_id]
        _save_notifications(notifications)
        
        return len(notifications) < original_count

def check_and_create_system_notifications() -> List[Dict]:
    """Check system status and create notifications for important events."""
    new_notifications = []
    
    try:
        health = get_system_health()
        health_status = health.get("status", "unknown")
        health_score = health.get("health_score", 100)
        
        if health_status == "unhealthy" or health_score < 50:
            new_notifications.append(create_notification(
                title="⚠️ System Health Alert",
                message=f"System health is {health_status} (score: {health_score}/100). Review system metrics.",
                type="warning",
                priority="high",
                category="system_health",
                action_url="/api/health/system"
            ))
        
        metrics = health.get("metrics", {})
        recent_errors = metrics.get("recent_errors_24h", 0)
        
        if recent_errors > 20:
            new_notifications.append(create_notification(
                title="🚨 High Error Rate",
                message=f"{recent_errors} errors detected in the last 24 hours. Review error logs.",
                type="error",
                priority="high",
                category="errors",
                action_url="/api/health/errors"
            ))
        
        rate_limited = metrics.get("rate_limit_status", {}).get("rate_limited", False)
        if rate_limited:
            new_notifications.append(create_notification(
                title="⏸️ Rate Limit Active",
                message="Message sending is currently rate-limited. Some messages may be delayed.",
                type="warning",
                priority="medium",
                category="rate_limits",
                action_url="/api/health/rate-limits"
            ))
        
        analytics_data = get_analytics()
        total_messages = analytics_data.get("total_messages", 0)
        
        if total_messages > 0 and total_messages % 100 == 0:
            new_notifications.append(create_notification(
                title="📊 Milestone Reached",
                message=f"Processed {total_messages} messages! Great progress.",
                type="success",
                priority="low",
                category="milestone",
                expires_in_hours=24
            ))
        
    except Exception as e:
        print(f"[Notifications] Error checking system: {e}")
    
    return new_notifications

def get_notification_stats() -> Dict:
    """Get notification statistics."""
    notifications = _load_notifications()
    
    unread = sum(1 for n in notifications if not n.get("read", False))
    by_type = {}
    by_priority = {}
    
    for notif in notifications:
        notif_type = notif.get("type", "unknown")
        priority = notif.get("priority", "normal")
        
        by_type[notif_type] = by_type.get(notif_type, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1
    
    return {
        "total": len(notifications),
        "unread": unread,
        "read": len(notifications) - unread,
        "by_type": by_type,
        "by_priority": by_priority
    }

