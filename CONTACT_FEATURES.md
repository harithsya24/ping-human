# Contact Management & Conversation Intelligence Features

## Overview

This system provides comprehensive contact management, conversation tracking, reply detection, and AI-powered message suggestions for iMessage conversations.

## Features

### 1. Contact Management (`contact_manager.py`)

- **Fetch Contacts**: Retrieve contacts from Series API
- **Contact Lookup**: Get contact information by phone number
- **Contact Caching**: In-memory cache for fast lookups
- **Contact Search**: Search contacts by name or phone number
- **Contact Updates**: Update contact information with latest interactions

**API Endpoints:**
- `GET /api/contacts` - Get all contacts
- `GET /api/contacts/<phone>` - Get contact by phone number
- `GET /api/contacts/search?q=<query>` - Search contacts

### 2. Conversation Tracking (`conversation_tracker.py`)

- **Thread Management**: Track complete conversation threads
- **Reply Detection**: Detect if a person has replied within a time window
- **Message History**: Store and retrieve message history with timestamps
- **Conversation Summaries**: Get statistics about conversations
- **Pending Replies**: Identify conversations that need responses

**API Endpoints:**
- `GET /api/conversations/<chat_id>/thread` - Get full conversation thread
- `GET /api/conversations/<chat_id>/summary` - Get conversation summary
- `GET /api/conversations/<chat_id>/has_replied?sender=<phone>&within_minutes=<minutes>` - Check if user replied
- `GET /api/conversations/pending?threshold_minutes=<minutes>` - Get pending replies

### 3. Next Message Generation (`next_message_generator.py`)

- **AI-Powered Suggestions**: Generate context-aware next messages
- **Follow-Up Messages**: Create follow-up messages after user responses
- **Multiple Options**: Generate multiple message options for scenarios
- **Language-Aware**: Respects user's language preferences

**API Endpoints:**
- `GET /api/conversations/<chat_id>/next_message?contact_name=<name>` - Get next message suggestion
- `POST /api/conversations/<chat_id>/follow_up` - Generate follow-up message
  ```json
  {
    "last_message": "User's last message",
    "contact_name": "Contact name (optional)"
  }
  ```
- `POST /api/conversations/<chat_id>/message_options` - Get multiple message options
  ```json
  {
    "scenario": "Description of scenario",
    "contact_name": "Contact name (optional)"
  }
  ```

### 4. Decision Support (`decision_support.py`)

- **Conversation Analysis**: Analyze conversation state and provide recommendations
- **Decision Support**: Get AI-powered decision support for questions
- **Send/Don't Send**: Determine if a message should be sent
- **Conversation Insights**: Get insights about conversation patterns

**API Endpoints:**
- `GET /api/conversations/<chat_id>/state` - Get conversation state analysis
- `GET /api/conversations/<chat_id>/should_send` - Check if message should be sent
- `POST /api/conversations/<chat_id>/decision_support` - Get decision support
  ```json
  {
    "question": "What should I do?",
    "contact_name": "Contact name (optional)"
  }
  ```
- `GET /api/conversations/<chat_id>/insights` - Get conversation insights

## Integration with Bot Service

The bot service (`backend/bot_service.py`) automatically:

1. **Tracks Messages**: Every message is added to conversation threads
2. **Detects Replies**: Checks if users have replied within time windows
3. **Manages Contacts**: Fetches and caches contact information
4. **Analyzes State**: Provides conversation state analysis for decision-making
5. **Logs Context**: Maintains full conversation context for AI responses

## Usage Examples

### Example 1: Check if User Replied

```python
from conversation_tracker import has_replied

# Check if user replied within last hour
if has_replied(chat_id, sender_phone, within_minutes=60):
    print("User has replied!")
```

### Example 2: Generate Next Message

```python
from next_message_generator import generate_next_message
from openai import OpenAI

ai_client = OpenAI(api_key="your-key")
suggestion = generate_next_message(chat_id, ai_client=ai_client, contact_name="John")
print(f"Suggested message: {suggestion}")
```

### Example 3: Get Decision Support

```python
from decision_support import get_decision_support

support = get_decision_support(
    chat_id,
    "Should I send a follow-up message?",
    ai_client=ai_client,
    contact_name="John"
)
print(f"Decision: {support['decision']}")
print(f"Reasoning: {support['reasoning']}")
```

### Example 4: Get Contact Information

```python
from contact_manager import get_contact_by_phone, get_contact_name

contact = get_contact_by_phone("+1234567890")
print(f"Contact name: {contact['name']}")

# Or just get the name
name = get_contact_name("+1234567890")
print(f"Name: {name}")
```

## Real-Life Scenarios

### Scenario 1: User Replies After Long Gap

The system detects when a user replies after a long period and can:
- Generate a reconnection message
- Reference previous conversation context
- Provide decision support on how to respond

### Scenario 2: Multiple Conversations

The system tracks all conversations and can:
- Identify which conversations need attention
- Prioritize based on urgency and time since last message
- Generate appropriate responses for each context

### Scenario 3: Contact Management

The system maintains contact information and can:
- Display contact names instead of phone numbers
- Track interaction history per contact
- Provide personalized responses based on contact preferences

## Data Persistence

Currently, contact and conversation data is stored in-memory. For production use, consider:
- Database storage for contacts
- Persistent conversation history
- Contact synchronization with Series API

## Future Enhancements

- Contact groups and tagging
- Conversation templates
- Automated follow-up scheduling
- Integration with CRM systems
- Advanced analytics and reporting

