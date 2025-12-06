"""Backend API server for PingHumans."""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Import analytics and other modules
from analytics import get_analytics
from ai_responder import conversation_history, user_languages
from rate_limit_checker import get_rate_limit_status
from series_api import get_user_connections
from contact_manager import get_all_contacts, get_contact_by_phone, get_contact_name, search_contacts, sync_from_macos_contacts
from conversation_tracker import get_conversation_thread, get_conversation_summary, get_all_threads, get_pending_replies, has_replied
from next_message_generator import generate_next_message, generate_follow_up_message, suggest_message_options
from decision_support import analyze_conversation_state, get_decision_support, should_send_message, get_conversation_insights
from guardrails import (
    get_guardrail_stats, check_user_status, flag_user, unblock_user,
    reset_user_flags, record_violation, violation_history, user_flags
)
from agent_orchestrator import process_user_request, get_action_suggestions
from contact_matcher import match_contact_to_request, find_contacts_by_category, get_contact_suggestions
from permission_manager import (
    check_contact_permission, request_contact_permission, grant_contact_permission,
    deny_contact_permission, get_permission_status, reset_permissions
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
    """Get connections for a specific user. Returns cached contacts since Series API doesn't have this endpoint."""
    from datetime import datetime
    try:
        # Since Series API doesn't have /api/users/<id>/connections, return cached contacts instead
        # Contacts are built automatically from incoming messages
        contacts = get_all_contacts()
        return jsonify({
            "user_id": user_id,
            "connections": contacts,
            "connection_count": len(contacts),
            "status": "success",
            "note": "Contacts built from incoming messages (Series API doesn't have contact endpoints)",
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
    """Get all contacts with detailed information."""
    # Check permission first
    if not check_contact_permission():
        return jsonify({
            "error": "Contact access permission required",
            "needs_permission": True,
            "message": "Please grant contact access permission first"
        }), 403
    
    contacts_list = get_all_contacts()
    
    # Format response with detailed info
    formatted_contacts = []
    for contact in contacts_list:
        formatted_contact = {
            "name": contact.get("name", "Unknown"),
            "display_name": contact.get("display_name", "Unknown"),
            "phone_number": contact.get("phone_number", ""),
            "source": contact.get("source", "unknown"),
            "message_count": contact.get("message_count", 0),
            "first_seen": contact.get("first_seen"),
            "last_interaction": contact.get("last_interaction"),
            "last_updated": contact.get("last_updated"),
            "preferred_language": contact.get("preferred_language"),
            "last_message": contact.get("last_message", "")[:100] if contact.get("last_message") else None,
            "metadata": contact.get("metadata", {}),
            "has_message_context": len(contact.get("message_context", [])) > 0,
            "message_context_count": len(contact.get("message_context", []))
        }
        formatted_contacts.append(formatted_contact)
    
    return jsonify({
        "contacts": formatted_contacts,
        "count": len(formatted_contacts),
        "summary": {
            "total_contacts": len(formatted_contacts),
            "from_iphone": len([c for c in formatted_contacts if c.get("source") == "iphone_message"]),
            "inferred": len([c for c in formatted_contacts if c.get("source") == "inferred"]),
            "total_messages": sum(c.get("message_count", 0) for c in formatted_contacts)
        }
    })

@app.route('/api/contacts/<phone>', methods=['GET'])
def get_contact(phone):
    """Get contact by phone number."""
    # Check permission first
    if not check_contact_permission():
        return jsonify({
            "error": "Contact access permission required",
            "needs_permission": True
        }), 403
    
    contact = get_contact_by_phone(phone)
    if contact:
        return jsonify(contact)
    return jsonify({"error": "Contact not found"}), 404

@app.route('/api/contacts/search', methods=['GET'])
def search_contacts_endpoint():
    """Search contacts by query."""
    # Check permission first
    if not check_contact_permission():
        return jsonify({
            "error": "Contact access permission required",
            "needs_permission": True
        }), 403
    
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

# =========================
# Multi-Agent System Endpoints
# =========================

@app.route('/api/agents/process', methods=['POST'])
def process_request():
    """Process a user request using the multi-agent system."""
    try:
        data = request.json
        request_text = data.get('request', '')
        chat_id = data.get('chat_id', 'default')
        
        if not request_text:
            return jsonify({"error": "request is required"}), 400
        
        user_phone = data.get('user_phone', 'unknown')
        result = process_user_request(request_text, chat_id, user_phone, ai_client=ai_client)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/match_contact', methods=['POST'])
def match_contact():
    """Match a request to a contact."""
    try:
        data = request.json
        request_text = data.get('request', '')
        
        if not request_text:
            return jsonify({"error": "request is required"}), 400
        
        match = match_contact_to_request(request_text, ai_client=ai_client)
        # Check permission first
        if not check_contact_permission():
            return jsonify({
                "success": False,
                "needs_permission": True,
                "message": "Contact access permission required. Please grant permission first."
            }), 403
        
        if match:
            return jsonify(match)
        else:
            return jsonify({
                "success": False,
                "message": "No matching contact found",
                "suggestions": [
                    {
                        "name": c.get("name") or c.get("display_name", "Unknown"),
                        "phone": c.get("phone_number", "")
                    }
                    for c in get_contact_suggestions(request_text, limit=3)
                ]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/suggestions', methods=['POST'])
def get_suggestions():
    """Get action suggestions for a request."""
    try:
        data = request.json
        request_text = data.get('request', '')
        
        if not request_text:
            return jsonify({"error": "request is required"}), 400
        
        suggestions = get_action_suggestions(request_text, ai_client=ai_client)
        return jsonify({
            "request": request_text,
            "suggestions": suggestions,
            "count": len(suggestions)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/category/<category>', methods=['GET'])
def get_contacts_by_category(category):
    """Get contacts by category."""
    try:
        # Check permission first
        if not check_contact_permission():
            return jsonify({
                "error": "Contact access permission required",
                "needs_permission": True
            }), 403
        
        contacts = find_contacts_by_category(category, ai_client=ai_client)
        return jsonify({
            "category": category,
            "contacts": contacts,
            "count": len(contacts)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/sync', methods=['POST'])
def sync_contacts():
    """Sync contacts from macOS Contacts app."""
    try:
        # Check permission first
        if not check_contact_permission():
            return jsonify({
                "error": "Contact access permission required",
                "needs_permission": True
            }), 403
        
        synced_count = sync_from_macos_contacts()
        return jsonify({
            "success": True,
            "synced_count": synced_count,
            "message": f"Synced {synced_count} contacts from macOS Contacts app"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Could not sync contacts from macOS Contacts app"
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 5001))  # Changed default to 5001 to avoid AirPlay conflict
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"[API] Starting server on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

