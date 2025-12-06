"""Backend API server for PingHumans."""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Import analytics and other modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analytics import get_analytics
from ai_responder import conversation_history, user_languages
from rate_limit_checker import get_rate_limit_status
from series_api import get_user_connections
from contact_manager import get_all_contacts, get_contact_by_phone, get_contact_name, search_contacts
from conversation_tracker import get_conversation_thread, get_conversation_summary, get_all_threads, get_pending_replies, has_replied
from next_message_generator import generate_next_message, generate_follow_up_message, suggest_message_options
from decision_support import analyze_conversation_state, get_decision_support, should_send_message, get_conversation_insights
from guardrails import (
    get_guardrail_stats, check_user_status, flag_user, unblock_user,
    reset_user_flags, record_violation, violation_history, user_flags
)
from openai import OpenAI
import os

load_dotenv()

# Initialize OpenAI client for AI features
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ai_client = None
if OPENAI_API_KEY:
    ai_client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # Enable CORS for frontend

# Serve frontend at root
@app.route('/')
def index():
    """Serve the frontend dashboard."""
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "PingHumans API"})

@app.route('/api/analytics', methods=['GET'])
def analytics():
    """Get current analytics data."""
    return jsonify(get_analytics())

@app.route('/api/conversations', methods=['GET'])
def conversations():
    """Get all conversation histories."""
    # Convert conversation history to a more readable format
    conversations_data = {}
    for chat_id, history in conversation_history.items():
        conversations_data[chat_id] = {
            "messages": history,
            "message_count": len(history),
            "language": user_languages.get(chat_id, "en")
        }
    return jsonify(conversations_data)

@app.route('/api/conversations/<chat_id>', methods=['GET'])
def get_conversation(chat_id):
    """Get conversation history for a specific chat."""
    if chat_id in conversation_history:
        return jsonify({
            "chat_id": chat_id,
            "messages": conversation_history[chat_id],
            "language": user_languages.get(chat_id, "en"),
            "message_count": len(conversation_history[chat_id])
        })
    return jsonify({"error": "Conversation not found"}), 404

@app.route('/api/stats', methods=['GET'])
def stats():
    """Get summary statistics."""
    analytics_data = get_analytics()
    rate_limit_status = get_rate_limit_status()
    return jsonify({
        "total_messages": analytics_data["total_messages"],
        "total_responses": analytics_data["total_responses"],
        "unique_users": len(analytics_data["users"]),
        "active_conversations": len(conversation_history),
        "sentiment_distribution": analytics_data["sentiment_counts"],
        "top_languages": dict(sorted(analytics_data["language_counts"].items(), key=lambda x: x[1], reverse=True)[:5]),
        "top_intents": dict(sorted(analytics_data["intent_counts"].items(), key=lambda x: x[1], reverse=True)[:5]),
        "rate_limit_status": rate_limit_status,
        "guardrail_stats": get_guardrail_stats()
    })

@app.route('/api/users/<user_id>/connections', methods=['GET'])
def user_connections(user_id):
    """Get connections for a specific user from Series API with better formatting."""
    from datetime import datetime
    try:
        result = get_user_connections(user_id)
        
        # If there's an error but we got a structured response, return it
        if "error" in result and result.get("status") != "success":
            status_code = 404 if "not found" in result.get("error", "").lower() else 500
            return jsonify(result), status_code
        
        # Return successful response with better formatting
        return jsonify({
            "user_id": user_id,
            "connections": result.get("connections", []),
            "connection_count": result.get("count", 0),
            "status": "success",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "user_id": user_id,
            "connections": [],
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500

# =========================
# Contact Management Endpoints
# =========================

@app.route('/api/contacts', methods=['GET'])
def contacts():
    """Get all contacts."""
    return jsonify({
        "contacts": get_all_contacts(),
        "count": len(get_all_contacts())
    })

@app.route('/api/contacts/<phone>', methods=['GET'])
def get_contact(phone):
    """Get contact by phone number."""
    contact = get_contact_by_phone(phone)
    if contact:
        return jsonify(contact)
    return jsonify({"error": "Contact not found"}), 404

@app.route('/api/contacts/search', methods=['GET'])
def search_contacts_endpoint():
    """Search contacts by query."""
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Query parameter 'q' required"}), 400
    results = search_contacts(query)
    return jsonify({
        "query": query,
        "results": results,
        "count": len(results)
    })

# =========================
# Conversation Thread Endpoints
# =========================

@app.route('/api/conversations/<chat_id>/thread', methods=['GET'])
def get_thread(chat_id):
    """Get conversation thread with full message history."""
    thread = get_conversation_thread(chat_id)
    summary = get_conversation_summary(chat_id)
    return jsonify({
        "chat_id": chat_id,
        "thread": thread,
        "summary": summary
    })

@app.route('/api/conversations/<chat_id>/summary', methods=['GET'])
def get_thread_summary(chat_id):
    """Get conversation summary."""
    summary = get_conversation_summary(chat_id)
    return jsonify(summary)

@app.route('/api/conversations/<chat_id>/has_replied', methods=['GET'])
def check_reply(chat_id):
    """Check if user has replied recently."""
    sender = request.args.get('sender')
    within_minutes = int(request.args.get('within_minutes', 60))
    if not sender:
        return jsonify({"error": "sender parameter required"}), 400
    replied = has_replied(chat_id, sender, within_minutes)
    return jsonify({
        "chat_id": chat_id,
        "sender": sender,
        "has_replied": replied,
        "within_minutes": within_minutes
    })

@app.route('/api/conversations/pending', methods=['GET'])
def pending_replies():
    """Get conversations pending replies."""
    threshold = int(request.args.get('threshold_minutes', 60))
    pending = get_pending_replies(threshold_minutes=threshold)
    return jsonify({
        "pending": pending,
        "count": len(pending),
        "threshold_minutes": threshold
    })

# =========================
# Next Message Generation Endpoints
# =========================

@app.route('/api/conversations/<chat_id>/next_message', methods=['GET'])
def next_message(chat_id):
    """Generate next message suggestion."""
    try:
        contact_name = request.args.get('contact_name')
        suggested = generate_next_message(chat_id, ai_client=ai_client, contact_name=contact_name)
        return jsonify({
            "chat_id": chat_id,
            "suggested_message": suggested,
            "contact_name": contact_name
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/follow_up', methods=['POST'])
def follow_up(chat_id):
    """Generate follow-up message after user's last message."""
    data = request.json
    last_message = data.get('last_message', '')
    contact_name = data.get('contact_name')
    
    if not last_message:
        return jsonify({"error": "last_message required"}), 400
    
    try:
        suggested = generate_follow_up_message(chat_id, last_message, ai_client=ai_client, contact_name=contact_name)
        return jsonify({
            "chat_id": chat_id,
            "follow_up_message": suggested,
            "contact_name": contact_name
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/message_options', methods=['POST'])
def message_options(chat_id):
    """Generate multiple message options for a scenario."""
    data = request.json
    scenario = data.get('scenario', '')
    contact_name = data.get('contact_name')
    
    if not scenario:
        return jsonify({"error": "scenario required"}), 400
    
    try:
        options = suggest_message_options(chat_id, scenario, ai_client=ai_client, contact_name=contact_name)
        return jsonify({
            "chat_id": chat_id,
            "scenario": scenario,
            "options": options,
            "contact_name": contact_name
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# Decision Support Endpoints
# =========================

@app.route('/api/conversations/<chat_id>/state', methods=['GET'])
def conversation_state(chat_id):
    """Get conversation state analysis."""
    try:
        state = analyze_conversation_state(chat_id, ai_client=ai_client)
        return jsonify(state)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/should_send', methods=['GET'])
def check_should_send(chat_id):
    """Check if a message should be sent."""
    try:
        decision = should_send_message(chat_id, ai_client=ai_client)
        return jsonify(decision)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/decision_support', methods=['POST'])
def decision_support(chat_id):
    """Get decision support for a question."""
    data = request.json
    question = data.get('question', '')
    contact_name = data.get('contact_name')
    
    if not question:
        return jsonify({"error": "question required"}), 400
    
    try:
        support = get_decision_support(chat_id, question, ai_client=ai_client, contact_name=contact_name)
        return jsonify(support)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/insights', methods=['GET'])
def conversation_insights(chat_id):
    """Get conversation insights."""
    try:
        insights = get_conversation_insights(chat_id, ai_client=ai_client)
        return jsonify(insights)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 5001))  # Changed default to 5001 to avoid AirPlay conflict
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"[API] Starting server on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

