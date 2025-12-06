"""Guardrails for content safety, moderation, and abuse prevention."""
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from openai import OpenAI

# Violation tracking
violation_history: Dict[str, List[dict]] = defaultdict(list)
user_flags: Dict[str, dict] = {}  # phone -> {reason, count, timestamp}

# Rate limiting per user
user_message_counts: Dict[str, List[datetime]] = defaultdict(list)

# Content filters
BLOCKED_PATTERNS = [
    r'\b(spam|scam|phishing|malware|virus)\b',
    r'http[s]?://(?!trusted-domain)',
    r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card patterns
]

HARMFUL_KEYWORDS = [
    'violence', 'threat', 'harm', 'attack', 'kill', 'hurt',
    'illegal', 'drugs', 'weapon', 'bomb', 'terrorism'
]

INAPPROPRIATE_KEYWORDS = [
    'hate', 'discrimination', 'racism', 'sexism', 'harassment',
    'abuse', 'bullying', 'offensive'
]

def check_content_safety(text: str, ai_client: Optional[OpenAI] = None) -> Dict:
    """Check if content is safe and appropriate."""
    text_lower = text.lower()
    
    # Check for blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return {
                "safe": False,
                "reason": "blocked_pattern",
                "severity": "high",
                "message": "Message contains blocked content"
            }
    
    # Check for harmful keywords
    harmful_found = [kw for kw in HARMFUL_KEYWORDS if kw in text_lower]
    if harmful_found:
        return {
            "safe": False,
            "reason": "harmful_content",
            "severity": "high",
            "keywords": harmful_found,
            "message": "Message contains potentially harmful content"
        }
    
    # Check for inappropriate keywords
    inappropriate_found = [kw for kw in INAPPROPRIATE_KEYWORDS if kw in text_lower]
    if inappropriate_found:
        return {
            "safe": False,
            "reason": "inappropriate_content",
            "severity": "medium",
            "keywords": inappropriate_found,
            "message": "Message contains inappropriate content"
        }
    
    # AI-powered safety check if available
    if ai_client:
        try:
            safety_check = ai_client.moderations.create(input=text)
            result = safety_check.results[0]
            
            if result.flagged:
                categories = [cat for cat, flagged in result.categories.__dict__.items() if flagged]
                return {
                    "safe": False,
                    "reason": "ai_moderation",
                    "severity": "high" if any(cat in ['violence', 'self-harm', 'sexual'] for cat in categories) else "medium",
                    "categories": categories,
                    "message": "Message flagged by content moderation"
                }
        except Exception as e:
            print(f"[Guardrails] AI moderation check failed: {e}")
    
    return {
        "safe": True,
        "reason": "passed",
        "severity": "low"
    }

def check_rate_limit(phone: str, max_messages_per_minute: int = 10, max_messages_per_hour: int = 50) -> Tuple[bool, str]:
    """Check if user is within rate limits."""
    now = datetime.now()
    
    # Clean old timestamps (older than 1 hour)
    user_message_counts[phone] = [
        ts for ts in user_message_counts[phone]
        if (now - ts).total_seconds() < 3600
    ]
    
    # Check per-minute limit
    recent_minute = [ts for ts in user_message_counts[phone] if (now - ts).total_seconds() < 60]
    if len(recent_minute) >= max_messages_per_minute:
        return False, f"Rate limit exceeded: {len(recent_minute)} messages in last minute (max: {max_messages_per_minute})"
    
    # Check per-hour limit
    if len(user_message_counts[phone]) >= max_messages_per_hour:
        return False, f"Rate limit exceeded: {len(user_message_counts[phone])} messages in last hour (max: {max_messages_per_hour})"
    
    return True, "ok"

def record_message(phone: str):
    """Record a message for rate limiting."""
    user_message_counts[phone].append(datetime.now())

def check_user_status(phone: str) -> Dict:
    """Check if user is blocked or flagged."""
    if phone in user_flags:
        flag_info = user_flags[phone]
        return {
            "allowed": False,
            "blocked": True,
            "reason": flag_info.get("reason", "unknown"),
            "flag_count": flag_info.get("count", 0),
            "flagged_at": flag_info.get("timestamp")
        }
    
    # Check violation history
    recent_violations = [
        v for v in violation_history[phone]
        if (datetime.now() - datetime.fromisoformat(v["timestamp"])).total_seconds() < 86400
    ]
    
    if len(recent_violations) >= 5:
        return {
            "allowed": False,
            "blocked": True,
            "reason": "too_many_violations",
            "violation_count": len(recent_violations)
        }
    
    return {
        "allowed": True,
        "blocked": False
    }

def flag_user(phone: str, reason: str, severity: str = "medium"):
    """Flag a user for violations."""
    if phone not in user_flags:
        user_flags[phone] = {
            "reason": reason,
            "count": 0,
            "timestamp": datetime.now().isoformat(),
            "severity": severity
        }
    
    user_flags[phone]["count"] += 1
    user_flags[phone]["last_violation"] = datetime.now().isoformat()
    
    # Auto-block after 3 flags
    if user_flags[phone]["count"] >= 3:
        user_flags[phone]["blocked"] = True
        print(f"[Guardrails] [WARNING] User {phone} auto-blocked after {user_flags[phone]['count']} violations")

def record_violation(phone: str, violation_type: str, details: Dict):
    """Record a safety violation."""
    violation_history[phone].append({
        "type": violation_type,
        "timestamp": datetime.now().isoformat(),
        "details": details
    })
    
    # Keep only last 100 violations per user
    if len(violation_history[phone]) > 100:
        violation_history[phone] = violation_history[phone][-100:]

def validate_response(response: str, ai_client: Optional[OpenAI] = None) -> Dict:
    """Validate AI-generated response before sending."""
    # Check length
    if len(response) > 2000:
        return {
            "valid": False,
            "reason": "too_long",
            "message": "Response exceeds maximum length"
        }
    
    # Check for empty or whitespace-only
    if not response.strip():
        return {
            "valid": False,
            "reason": "empty",
            "message": "Response is empty"
        }
    
    # Safety check
    safety = check_content_safety(response, ai_client)
    if not safety["safe"]:
        return {
            "valid": False,
            "reason": "unsafe_response",
            "safety_check": safety,
            "message": "Response failed safety check"
        }
    
    return {
        "valid": True,
        "reason": "passed"
    }

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks."""
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Limit length
    if len(text) > 5000:
        text = text[:5000]
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def get_guardrail_stats() -> Dict:
    """Get statistics about guardrail enforcement."""
    total_violations = sum(len(v) for v in violation_history.values())
    flagged_users = len([u for u in user_flags.values() if u.get("blocked", False)])
    
    violation_types = defaultdict(int)
    for violations in violation_history.values():
        for v in violations:
            violation_types[v["type"]] += 1
    
    return {
        "total_violations": total_violations,
        "flagged_users": flagged_users,
        "active_flags": len(user_flags),
        "violation_types": dict(violation_types),
        "rate_limited_users": len([p for p, msgs in user_message_counts.items() if len(msgs) > 10])
    }

def unblock_user(phone: str):
    """Unblock a user."""
    if phone in user_flags:
        user_flags[phone]["blocked"] = False
        user_flags[phone]["unblocked_at"] = datetime.now().isoformat()
        print(f"[Guardrails] [OK] User {phone} unblocked")

def reset_user_flags(phone: str):
    """Reset flags for a user."""
    if phone in user_flags:
        del user_flags[phone]
    if phone in violation_history:
        violation_history[phone] = []
    if phone in user_message_counts:
        user_message_counts[phone] = []
    print(f"[Guardrails] [OK] User {phone} flags reset")

