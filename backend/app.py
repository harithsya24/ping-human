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
from action_history import get_action_history, get_action_summary, get_action_status, log_action
from conversation_export import export_conversation_json, export_conversation_csv, export_conversation_pdf, export_all_conversations_json
from advanced_analytics import get_all_advanced_analytics, get_peak_hours, get_sentiment_trends, get_response_time_metrics, get_engagement_metrics, get_message_volume_metrics
from conversation_search import search_conversations, get_conversation_search_suggestions
from contact_relationship_gnn import (
    add_relationship, get_relationship_graph_data, get_contact_communities,
    predict_relationships, infer_relationships_from_interactions, load_relationships
)
from conversation_tracker import conversation_threads
from message_templates import (
    create_template, get_template, get_all_templates, update_template,
    delete_template, render_template, get_template_categories
)
from contact_groups import (
    create_group, add_contact_to_group, remove_contact_from_group,
    get_group, get_all_groups, delete_group, add_tag_to_contact,
    remove_tag_from_contact, get_contact_tags, get_contacts_by_tag,
    get_all_tags, get_contacts_by_group
)
from system_health import (
    get_system_health, get_latency_metrics, get_error_breakdown,
    get_rate_limit_metrics, get_failed_actions_summary
)
from smart_reply_generator import generate_smart_replies
from weekly_insights import generate_weekly_report
from smart_notifications import (
    create_notification, get_notifications, mark_notification_read,
    mark_all_read, delete_notification, check_and_create_system_notifications,
    get_notification_stats
)
from conversation_timeline import (
    get_conversation_timeline, get_all_timelines, get_timeline_summary,
    get_timeline_visualization_data
)
from notification_preferences import (
    get_preferences, update_preferences, should_send_proactive_reminder,
    get_reminder_times, get_urgent_email_limit
)
from memory_retrieval import (
    is_memory_retrieval_request, get_conversation_by_id,
    search_conversations_by_date, search_conversations_by_date_range,
    get_user_messages_only, search_by_keyword
)
from flask import Response
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
    # COMMENTED OUT: Contact permission check - allow access regardless of permission status
    # if not check_contact_permission():
    #     return jsonify({
    #         "error": "Contact access permission required",
    #         "needs_permission": True,
    #         "message": "Please grant contact access permission first"
    #     }), 403
    
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
    # COMMENTED OUT: Contact permission check - allow access regardless of permission status
    # if not check_contact_permission():
    #     return jsonify({
    #         "error": "Contact access permission required",
    #         "needs_permission": True
    #     }), 403
    
    contact = get_contact_by_phone(phone)
    if contact:
        return jsonify(contact)
    return jsonify({"error": "Contact not found"}), 404

@app.route('/api/contacts/search', methods=['GET'])
def search_contacts_endpoint():
    """Search contacts by query."""
    # COMMENTED OUT: Contact permission check - allow access regardless of permission status
    # if not check_contact_permission():
    #     return jsonify({
    #         "error": "Contact access permission required",
    #         "needs_permission": True
    #     }), 403
    
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
        
        # Check permission FIRST before any contact access
        # COMMENTED OUT: Contact permission check - allow access regardless of permission status
        # if not check_contact_permission():
        #     return jsonify({
        #         "success": False,
        #         "needs_permission": True,
        #         "message": "Contact access permission required. Please grant permission first."
        #     }), 403
        
        # Now safe to access contacts
        match = match_contact_to_request(request_text, ai_client=ai_client)
        
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
        # COMMENTED OUT: Contact permission check - allow access regardless of permission status
        # if not check_contact_permission():
        #     return jsonify({
        #         "error": "Contact access permission required",
        #         "needs_permission": True
        #     }), 403
        
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
        # COMMENTED OUT: Contact permission check - allow access regardless of permission status
        # if not check_contact_permission():
        #     return jsonify({
        #         "error": "Contact access permission required",
        #         "needs_permission": True
        #     }), 403
        
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

@app.route('/api/contacts/relationships', methods=['GET'])
def get_contact_relationships():
    """Get contact relationship graph data for visualization."""
    try:
        contacts = get_all_contacts()
        graph_data = get_relationship_graph_data(contacts)
        return jsonify(graph_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/relationships', methods=['POST'])
def create_relationship():
    """Add a relationship between two contacts."""
    try:
        data = request.json
        contact1 = data.get("contact1")
        contact2 = data.get("contact2")
        relationship_type = data.get("type", "unknown")
        strength = data.get("strength", 1.0)
        
        if not contact1 or not contact2:
            return jsonify({"error": "contact1 and contact2 are required"}), 400
        
        add_relationship(contact1, contact2, relationship_type, strength)
        return jsonify({"success": True, "message": "Relationship added"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/communities', methods=['GET'])
def get_communities():
    """Get contact communities detected by GNN."""
    try:
        contacts = get_all_contacts()
        communities = get_contact_communities(contacts)
        return jsonify({
            "success": True,
            "communities": communities,
            "total_communities": len(communities)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/relationships/predict', methods=['GET'])
def predict_contact_relationships():
    """Use GNN to predict relationships between contacts."""
    try:
        contacts = get_all_contacts()
        predictions = predict_relationships(contacts)
        return jsonify({
            "success": True,
            "predictions": predictions,
            "count": len(predictions)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/relationships/infer', methods=['POST'])
def infer_relationships():
    """Infer relationships from conversation patterns using GNN."""
    try:
        contacts = get_all_contacts()
        inferred = infer_relationships_from_interactions(contacts, conversation_threads)
        return jsonify({
            "success": True,
            "inferred_relationships": inferred,
            "count": len(inferred)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/relationships/all', methods=['GET'])
def get_all_relationships():
    """Get all stored relationships."""
    try:
        data = load_relationships()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get all message templates."""
    try:
        category = request.args.get('category')
        templates = get_all_templates(category=category)
        return jsonify({
            "success": True,
            "templates": templates,
            "count": len(templates)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates', methods=['POST'])
def create_template_endpoint():
    """Create a new message template."""
    try:
        data = request.json
        name = data.get("name")
        content = data.get("content")
        category = data.get("category", "general")
        variables = data.get("variables", [])
        
        if not name or not content:
            return jsonify({"error": "name and content are required"}), 400
        
        template = create_template(name, content, category, variables)
        return jsonify({"success": True, "template": template})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates/<template_id>', methods=['GET'])
def get_template_endpoint(template_id):
    """Get a template by ID."""
    try:
        template = get_template(template_id)
        if template:
            return jsonify({"success": True, "template": template})
        return jsonify({"error": "Template not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates/<template_id>', methods=['PUT'])
def update_template_endpoint(template_id):
    """Update a template."""
    try:
        data = request.json
        template = update_template(
            template_id,
            name=data.get("name"),
            content=data.get("content"),
            category=data.get("category")
        )
        if template:
            return jsonify({"success": True, "template": template})
        return jsonify({"error": "Template not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates/<template_id>', methods=['DELETE'])
def delete_template_endpoint(template_id):
    """Delete a template."""
    try:
        success = delete_template(template_id)
        if success:
            return jsonify({"success": True, "message": "Template deleted"})
        return jsonify({"error": "Template not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates/<template_id>/render', methods=['POST'])
def render_template_endpoint(template_id):
    """Render a template with variables."""
    try:
        data = request.json
        variables = data.get("variables", {})
        
        rendered = render_template(template_id, variables)
        if rendered:
            return jsonify({"success": True, "rendered_text": rendered})
        return jsonify({"error": "Template not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates/categories', methods=['GET'])
def get_template_categories_endpoint():
    """Get all template categories."""
    try:
        categories = get_template_categories()
        return jsonify({"success": True, "categories": categories})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/groups', methods=['GET'])
def get_groups():
    """Get all contact groups."""
    try:
        groups = get_all_groups()
        return jsonify({
            "success": True,
            "groups": groups,
            "count": len(groups)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/groups', methods=['POST'])
def create_group_endpoint():
    """Create a new contact group."""
    try:
        data = request.json
        name = data.get("name")
        description = data.get("description")
        color = data.get("color")
        
        if not name:
            return jsonify({"error": "name is required"}), 400
        
        group = create_group(name, description, color)
        return jsonify({"success": True, "group": group})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/groups/<group_id>', methods=['GET'])
def get_group_endpoint(group_id):
    """Get a group by ID."""
    try:
        group = get_group(group_id)
        if group:
            return jsonify({"success": True, "group": group})
        return jsonify({"error": "Group not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/groups/<group_id>', methods=['DELETE'])
def delete_group_endpoint(group_id):
    """Delete a group."""
    try:
        success = delete_group(group_id)
        if success:
            return jsonify({"success": True, "message": "Group deleted"})
        return jsonify({"error": "Group not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/groups/<group_id>/contacts', methods=['POST'])
def add_contact_to_group_endpoint(group_id):
    """Add a contact to a group."""
    try:
        data = request.json
        contact_id = data.get("contact_id")
        
        if not contact_id:
            return jsonify({"error": "contact_id is required"}), 400
        
        success = add_contact_to_group(group_id, contact_id)
        if success:
            return jsonify({"success": True, "message": "Contact added to group"})
        return jsonify({"error": "Group not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/groups/<group_id>/contacts/<contact_id>', methods=['DELETE'])
def remove_contact_from_group_endpoint(group_id, contact_id):
    """Remove a contact from a group."""
    try:
        success = remove_contact_from_group(group_id, contact_id)
        if success:
            return jsonify({"success": True, "message": "Contact removed from group"})
        return jsonify({"error": "Group or contact not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/tags', methods=['GET'])
def get_all_tags_endpoint():
    """Get all tags."""
    try:
        tags = get_all_tags()
        return jsonify({"success": True, "tags": tags})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/<contact_id>/tags', methods=['GET'])
def get_contact_tags_endpoint(contact_id):
    """Get tags for a contact."""
    try:
        tags = get_contact_tags(contact_id)
        return jsonify({"success": True, "tags": tags})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/<contact_id>/tags', methods=['POST'])
def add_tag_to_contact_endpoint(contact_id):
    """Add a tag to a contact."""
    try:
        data = request.json
        tag = data.get("tag")
        
        if not tag:
            return jsonify({"error": "tag is required"}), 400
        
        success = add_tag_to_contact(contact_id, tag)
        return jsonify({"success": success, "message": "Tag added" if success else "Tag already exists"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/<contact_id>/tags/<tag>', methods=['DELETE'])
def remove_tag_from_contact_endpoint(contact_id, tag):
    """Remove a tag from a contact."""
    try:
        success = remove_tag_from_contact(contact_id, tag)
        return jsonify({"success": success, "message": "Tag removed" if success else "Tag not found"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/contacts/tags/<tag>', methods=['GET'])
def get_contacts_by_tag_endpoint(tag):
    """Get all contacts with a specific tag."""
    try:
        contacts = get_contacts_by_tag(tag)
        return jsonify({"success": True, "contacts": contacts, "count": len(contacts)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health/system', methods=['GET'])
def system_health():
    """Get system health metrics."""
    try:
        health = get_system_health()
        return jsonify(health)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health/latency', methods=['GET'])
def latency_metrics():
    """Get latency metrics."""
    try:
        metrics = get_latency_metrics()
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health/errors', methods=['GET'])
def error_breakdown():
    """Get error breakdown."""
    try:
        breakdown = get_error_breakdown()
        return jsonify(breakdown)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health/rate-limits', methods=['GET'])
def rate_limit_metrics():
    """Get rate limit metrics."""
    try:
        metrics = get_rate_limit_metrics()
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/actions', methods=['GET'])
def get_actions():
    """Get action history for recent activity display."""
    try:
        limit = request.args.get('limit', 20, type=int)
        action_type = request.args.get('type')
        
        # Get action history
        history = get_action_history(action_type=action_type, limit=limit)
        
        # Format actions for frontend
        actions = []
        for entry in history:
            if not entry:
                continue
            try:
                action = {
                    "id": entry.get("id", ""),
                    "timestamp": entry.get("timestamp", ""),
                    "action_type": entry.get("action_type", ""),
                    "status": get_action_status(entry),
                    "summary": get_action_summary(entry),
                    "details": entry.get("details", {})
                }
                actions.append(action)
            except Exception as e:
                print(f"[API] Error formatting action entry: {e}")
                continue
        
        return jsonify({
            "success": True,
            "actions": actions,
            "count": len(actions)
        })
    except Exception as e:
        import traceback
        print(f"[API] Error in /api/actions: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "actions": []
        }), 500

@app.route('/api/health/failed-actions', methods=['GET'])
def failed_actions():
    """Get failed actions summary."""
    try:
        summary = get_failed_actions_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/smart-replies', methods=['GET'])
def get_smart_replies(chat_id):
    """Get smart reply suggestions for a conversation."""
    try:
        last_message = request.args.get('last_message', '')
        num_suggestions = request.args.get('num', type=int, default=4)
        
        suggestions = generate_smart_replies(chat_id, last_message, ai_client, num_suggestions)
        return jsonify({
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/insights/weekly', methods=['GET'])
def weekly_insights():
    """Get weekly insights report."""
    try:
        report = generate_weekly_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications', methods=['GET'])
def get_notifications_endpoint():
    """Get notifications."""
    try:
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        limit = request.args.get('limit', type=int, default=50)
        
        notifications = get_notifications(unread_only=unread_only, limit=limit)
        stats = get_notification_stats()
        
        return jsonify({
            "success": True,
            "notifications": notifications,
            "count": len(notifications),
            "stats": stats
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications', methods=['POST'])
def create_notification_endpoint():
    """Create a notification."""
    try:
        data = request.json
        title = data.get("title")
        message = data.get("message")
        notif_type = data.get("type", "info")
        priority = data.get("priority", "normal")
        category = data.get("category")
        action_url = data.get("action_url")
        expires_in_hours = data.get("expires_in_hours")
        
        if not title or not message:
            return jsonify({"error": "title and message are required"}), 400
        
        notification = create_notification(
            title, message, notif_type, priority, category, action_url, expires_in_hours
        )
        return jsonify({"success": True, "notification": notification})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/check', methods=['POST'])
def check_system_notifications():
    """Check system and create notifications for important events."""
    try:
        new_notifications = check_and_create_system_notifications()
        return jsonify({
            "success": True,
            "notifications_created": len(new_notifications),
            "notifications": new_notifications
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
def mark_notification_read_endpoint(notification_id):
    """Mark a notification as read."""
    try:
        success = mark_notification_read(notification_id)
        if success:
            return jsonify({"success": True, "message": "Notification marked as read"})
        return jsonify({"error": "Notification not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/read-all', methods=['POST'])
def mark_all_read_endpoint():
    """Mark all notifications as read."""
    try:
        count = mark_all_read()
        return jsonify({"success": True, "count": count, "message": f"Marked {count} notifications as read"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/<notification_id>', methods=['DELETE'])
def delete_notification_endpoint(notification_id):
    """Delete a notification."""
    try:
        success = delete_notification(notification_id)
        if success:
            return jsonify({"success": True, "message": "Notification deleted"})
        return jsonify({"error": "Notification not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/stats', methods=['GET'])
def notification_stats():
    """Get notification statistics."""
    try:
        stats = get_notification_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/timeline', methods=['GET'])
def get_conversation_timeline_endpoint(chat_id):
    """Get conversation timeline data."""
    try:
        timeline = get_conversation_timeline(chat_id)
        return jsonify(timeline)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/timelines', methods=['GET'])
def get_all_timelines_endpoint():
    """Get timelines for all conversations."""
    try:
        timelines = get_all_timelines()
        return jsonify({
            "success": True,
            "timelines": timelines,
            "count": len(timelines)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/timeline/summary', methods=['GET'])
def get_timeline_summary_endpoint(chat_id):
    """Get timeline summary."""
    try:
        summary = get_timeline_summary(chat_id)
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/conversations/<chat_id>/timeline/visualization', methods=['GET'])
def get_timeline_visualization_endpoint(chat_id):
    """Get timeline data for visualization."""
    try:
        data = get_timeline_visualization_data(chat_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/preferences', methods=['GET'])
def get_notification_preferences():
    """Get notification preferences."""
    try:
        prefs = get_preferences()
        return jsonify(prefs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/preferences', methods=['PUT'])
def update_notification_preferences():
    """Update notification preferences."""
    try:
        data = request.json
        prefs = update_preferences(**data)
        return jsonify({"success": True, "preferences": prefs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memory/conversation/<chat_id>', methods=['GET'])
def get_conversation_memory(chat_id):
    """Get conversation by ID from memory (exact matches only)."""
    try:
        result = get_conversation_by_id(chat_id)
        if result:
            return jsonify({"success": True, "conversation": result})
        return jsonify({
            "success": False,
            "message": "I cannot find that information in the stored conversation history."
        }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memory/date', methods=['GET'])
def search_memory_by_date():
    """Search conversations by date (exact matches only)."""
    try:
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({"error": "date parameter is required"}), 400
        
        results = search_conversations_by_date(date_str)
        if results:
            return jsonify({"success": True, "results": results, "count": len(results)})
        return jsonify({
            "success": False,
            "message": "I cannot find that information in the stored conversation history.",
            "results": []
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memory/date-range', methods=['GET'])
def search_memory_by_date_range():
    """Search conversations by date range (exact matches only)."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date parameters are required"}), 400
        
        results = search_conversations_by_date_range(start_date, end_date)
        if results:
            return jsonify({"success": True, "results": results, "count": len(results)})
        return jsonify({
            "success": False,
            "message": "I cannot find that information in the stored conversation history.",
            "results": []
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memory/user-messages', methods=['GET'])
def get_user_messages_memory():
    """Get user messages only (exact matches only)."""
    try:
        chat_id = request.args.get('chat_id')
        date = request.args.get('date')
        
        results = get_user_messages_only(chat_id=chat_id, date=date)
        if results:
            return jsonify({"success": True, "messages": results, "count": len(results)})
        return jsonify({
            "success": False,
            "message": "I cannot find that information in the stored conversation history.",
            "messages": []
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memory/search', methods=['GET'])
def search_memory_by_keyword():
    """Search messages by keyword (exact matches only)."""
    try:
        keyword = request.args.get('keyword') or request.args.get('q')
        chat_id = request.args.get('chat_id')
        
        if not keyword:
            return jsonify({"error": "keyword or q parameter is required"}), 400
        
        results = search_by_keyword(keyword, chat_id=chat_id)
        if results:
            return jsonify({"success": True, "results": results, "count": len(results)})
        return jsonify({
            "success": False,
            "message": "I cannot find that information in the stored conversation history.",
            "results": []
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"[API] Starting server on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

