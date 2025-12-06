"""Analytics tracking functionality."""
import json
import os
from datetime import datetime
from threading import Lock

# File to persist analytics (shared between bot service and API server)
ANALYTICS_FILE = "analytics_data.json"
_analytics_lock = Lock()

def _load_analytics():
    """Load analytics from file or return default."""
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Analytics] Error loading: {e}")
    return {
        "total_messages": 0,
        "total_responses": 0,
        "sentiment_counts": {"positive": 0, "neutral": 0, "negative": 0},
        "intent_counts": {},
        "language_counts": {},
        "users": {}
    }

def _save_analytics(data):
    """Save analytics to file."""
    try:
        with open(ANALYTICS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Analytics] Error saving: {e}")

# Analytics tracking (loaded from file)
analytics = _load_analytics()

def update_analytics(sender: str, text: str, analysis: dict):
    """Update analytics tracking."""
    with _analytics_lock:
        # Reload to get latest data from file
        analytics.update(_load_analytics())
        
        analytics["total_messages"] += 1
        
        # Track sentiment
        sentiment = analysis.get("sentiment", "neutral")
        if sentiment in analytics["sentiment_counts"]:
            analytics["sentiment_counts"][sentiment] += 1
        
        # Track intent
        intent = analysis.get("intent", "general")
        analytics["intent_counts"][intent] = analytics["intent_counts"].get(intent, 0) + 1
        
        # Track language
        language = analysis.get("language", "en")
        analytics["language_counts"][language] = analytics["language_counts"].get(language, 0) + 1
        
        # Track user
        if sender not in analytics["users"]:
            analytics["users"][sender] = {"message_count": 0, "first_seen": None, "preferred_language": language}
        analytics["users"][sender]["message_count"] += 1
        if not analytics["users"][sender]["first_seen"]:
            analytics["users"][sender]["first_seen"] = datetime.now().isoformat()
        # Update preferred language if detected
        if language != "en":  # Only update if not English
            analytics["users"][sender]["preferred_language"] = language
        
        # Save to file so API server can read it
        _save_analytics(analytics)

def record_response():
    """Record that a response was sent."""
    with _analytics_lock:
        analytics.update(_load_analytics())
        analytics["total_responses"] += 1
        _save_analytics(analytics)

def print_analytics():
    """Print current analytics summary."""
    with _analytics_lock:
        analytics.update(_load_analytics())
    print("\n" + "="*50)
    print("[Analytics] Current Stats:")
    print(f"  Total Messages: {analytics['total_messages']}")
    print(f"  Total Responses: {analytics['total_responses']}")
    print(f"  Sentiment: {analytics['sentiment_counts']}")
    print(f"  Top Intents: {dict(sorted(analytics['intent_counts'].items(), key=lambda x: x[1], reverse=True)[:5])}")
    print(f"  Languages: {dict(sorted(analytics['language_counts'].items(), key=lambda x: x[1], reverse=True)[:5])}")
    print(f"  Unique Users: {len(analytics['users'])}")
    print("="*50 + "\n")

def get_analytics():
    """Get current analytics data."""
    with _analytics_lock:
        # Reload to get latest data from file
        analytics.update(_load_analytics())
        return analytics.copy()
