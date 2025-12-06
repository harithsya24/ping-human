# PingHumans

**AI-Powered iMessage Assistant Built on Series Platform**

PingHumans is an intelligent messaging bot that leverages the **Series iMessage Service API** to provide AI-powered conversational assistance, contact management, and proactive communication features through iMessage.

---

## 👤 Authors

**Amrutha Kanakatte Ravishankar, Sneha Venkatesh**
- 📧 Email: amruthakravishankar@outlook.com; venkateshsneha30@gmail.com
- 💻 GitHub: [harithsya24](https://github.com/harithsya24)

---

## 🎯 Series Platform Integration

### Core Series Features

**Series iMessage Service API** is the foundation of PingHumans, enabling:

- **📨 Message Sending** - Send iMessages via Series API (`/api/chats/{chat_id}/chat_messages`)
- **💬 Chat Creation** - Create new chats and initiate conversations (`/api/chats`)
- **👥 User Connections** - Access user connections and contact information (`/api/users/{user_id}/connections`)
- **📡 Kafka Event Consumption** - Real-time message processing from Kafka topics
- **🔄 Event Handling** - Process `message.received`, `typing_indicator` events
- **📞 Contact Extraction** - Extract contacts from `chat_handles` in Kafka events

### Series API Capabilities

- **Rate Limit Handling** - Automatic detection and handling of 429 (rate limit) responses
- **Quota Management** - Error handling for 403 (forbidden/quota exceeded) responses
- **Phone Number Validation** - Cleans and validates phone numbers before API calls
- **Error Recovery** - Robust error handling with detailed logging
- **Connection Management** - Automatic reconnection on connection loss

---

## 🚀 Additional Features

### 🤖 AI & Natural Language Processing

- **LLM-Powered Responses** - Context-aware replies using OpenAI GPT-4o-mini
- **Long Context Awareness** - Maintains conversation history up to 200 messages
- **Few-Shot Learning** - Uses conversation history as examples for better responses
- **Topic Adherence** - Stays on topic, understands context (e.g., "hospital in NYC" = hospitals, not tourism)
- **Conversation Summarization** - AI-generated summaries of long conversations
- **Intent Detection** - Identifies user intent (question, complaint, request, greeting, etc.)
- **Sentiment Analysis** - Analyzes message sentiment (positive, neutral, negative)
- **Urgency Detection** - Identifies urgent messages requiring immediate attention

### 🌍 Multilingual Support

- **Language Detection** - Automatically detects 20+ languages including:
  - English, Kannada, Tamil, Telugu, Hindi, Malayalam, and more
- **Language-Aware Responses** - Responds in the user's detected language
- **Translation Verification** - Ensures accurate translations for non-English languages
- **Language Statistics** - Tracks language usage across conversations

### 📱 Contact Management & Multi-Agent System

- **Smart Contact Matching** - AI-powered contact search and matching
- **Contact-Based Actions**:
  - **Order** - "Order pizza" → finds "Pizza Guy" → sends order message
  - **Book** - "Book appointment" → matches contact → schedules
  - **Call** - "Call doctor" → finds contact → initiates call
  - **Message** - "Message mom" → finds contact → sends message
  - **Email** - "Email client" → finds contact → sends email
- **macOS Contacts Integration** - Syncs contacts from macOS Contacts app
- **Contact Extraction** - Automatically extracts contacts from iMessage `chat_handles`
- **Contact Caching** - Efficient in-memory contact cache
- **Contact Suggestions** - Provides suggestions when exact match not found
- **Permission Management** - Secure permission system for contact access

### 📧 Email & Calendar Integration

- **Gmail API Integration** - Reads emails via Gmail API
- **ML-Based Email Classification** - Uses AI to filter urgent emails, avoids spam
- **Meeting Detection** - Extracts meeting information from emails
- **Google Calendar Integration** - Reads upcoming meetings from Google Calendar
- **macOS Calendar (iCalendar)** - Integrates with macOS Calendar app
- **Unified Meeting View** - Combines meetings from all sources (Gmail, Google Calendar, iCalendar)
- **Meeting Reminders** - Automatic reminders at:
  - 1 day before
  - 1 hour before
  - 30 minutes before
  - 5 minutes before
- **Urgent Email Alerts** - Sends notifications for urgent emails (max 3 per check)
- **Meeting Queries** - Natural language queries: "Any meetings for me?" or "Any urgent emails?"

### 🛡️ Safety & Guardrails

- **Content Safety** - Pattern-based content filtering
- **AI Moderation** - AI-powered content moderation
- **Rate Limiting** - Tracks and enforces message limits per hour/day
- **User Management** - User blocking, flagging, and violation tracking
- **Input Sanitization** - Prevents injection attacks
- **Response Validation** - Validates AI responses before sending
- **Permission Checks** - All contact access requires explicit permission

### 📊 Analytics & Dashboard

- **Real-Time Dashboard** - Beautiful web UI at `http://localhost:5001`
- **Auto-Refresh** - Dashboard updates every 5 seconds
- **Analytics Tracking**:
  - Message and response counts
  - Sentiment distribution
  - Language statistics
  - Intent analysis
  - Per-user analytics
- **Recent Activity** - Shows top 5 most recent conversations
- **Rate Limit Status** - Displays current API quota status
- **Guardrail Statistics** - Shows safety and moderation stats
- **File-Based Persistence** - Analytics stored in `analytics_data.json`

### 💬 Conversation Intelligence

- **Thread Tracking** - Maintains conversation threads per chat
- **Reply Detection** - Detects replies within time windows
- **Pending Replies** - Identifies conversations needing responses
- **Next Message Generation** - Suggests next messages based on context
- **Follow-Up Messages** - Generates contextual follow-ups
- **Decision Support** - Analyzes conversation state and recommends actions
- **Conversation Insights** - Provides insights into conversation patterns

### ⚡ Proactive Features

- **Proactive Messaging** - Automatically checks in with users after inactivity
- **Time-Based Triggers** - Sends messages based on time patterns
- **Context-Aware Follow-Ups** - Follows up based on conversation history
- **Reminder Scheduling** - Background thread for meeting and email reminders

### 🔧 Technical Features

- **Modular Architecture** - 29 Python modules in `backend/` directory
- **REST API** - 20+ endpoints for analytics, contacts, conversations, agents
- **Error Handling** - Robust error handling throughout
- **Auto-Reconnect** - Automatically reconnects if Kafka connection is lost
- **Multi-Step Actions** - Handles confirmations and detail collection
- **Thread-Safe Operations** - Safe concurrent access to shared data
- **Data Persistence** - File-based storage for analytics, permissions, pending actions

---

## 📁 Project Structure

```
ping-human/
├── backend/                    # All Python modules (29 files)
│   ├── app.py                 # Flask REST API server
│   ├── bot_service.py         # Kafka consumer & message processing
│   ├── series_api.py          # Series API client
│   ├── kafka_consumer.py      # Kafka consumer module
│   ├── ai_responder.py        # AI response generation
│   ├── sentiment_analyzer.py  # Sentiment & intent analysis
│   ├── language_detector.py   # Language detection
│   ├── contact_manager.py     # Contact management
│   ├── contact_matcher.py     # Contact matching
│   ├── agent_orchestrator.py  # Multi-agent orchestrator
│   ├── action_executor.py     # Action execution
│   ├── conversation_tracker.py # Conversation tracking
│   ├── next_message_generator.py # Next message suggestions
│   ├── decision_support.py    # Decision support
│   ├── guardrails.py          # Safety & moderation
│   ├── permission_manager.py # Permission management
│   ├── pending_actions.py     # Multi-step action tracking
│   ├── analytics.py           # Analytics tracking
│   ├── proactive_messenger.py # Proactive messaging
│   ├── rate_limit_checker.py  # Rate limiting
│   ├── gmail_client.py        # Gmail API integration
│   ├── meeting_detector.py    # Meeting detection
│   ├── meeting_checker.py     # Meeting queries
│   ├── reminder_scheduler.py  # Reminder scheduling
│   ├── icalendar_client.py    # macOS Calendar integration
│   ├── macos_contacts.py      # macOS Contacts integration
│   ├── email_client.py        # Email sending
│   └── list_contacts.py       # Contact listing utility
├── frontend/
│   └── index.html             # Real-time analytics dashboard
├── main.py                    # (Legacy - use backend/bot_service.py)
├── requirements.txt           # Python dependencies
├── env.example                # Environment variables template
├── start_bot.sh              # Start bot service script
├── start_backend.sh          # Start API server script
└── start_all.sh              # Start both services script
```

---

## 🛠️ Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `env.example` to `.env` and fill in your credentials:

```bash
cp env.example .env
```

**Required Configuration:**
- `SERIES_API_KEY` - Your Series API key
- `SERIES_API_BASE_URL` - Series API base URL
- `SENDER_NUMBER` - Your iMessage sender number
- `KAFKA_*` - Kafka configuration (bootstrap servers, topic, credentials)
- `OPENAI_API_KEY` - OpenAI API key for AI features

**Optional Configuration:**
- `GMAIL_CREDENTIALS_FILE` - Path to Gmail OAuth credentials (for email/calendar features)
- `API_PORT` - Port for Flask API server (default: 5001)

### 3. Gmail/Calendar Setup (Optional)

1. Download `credentials.json` from Google Cloud Console
2. Place it in the project root
3. Run the bot - it will prompt for OAuth authentication on first run
4. Grant Calendar and Gmail permissions

---

## 🚀 Running the Application

### Option 1: Start Everything Together

```bash
./start_all.sh
```

### Option 2: Run Separately

**Terminal 1 - Bot Service** (processes messages from Series/Kafka):
```bash
./start_bot.sh
# or
python3 backend/bot_service.py
```

**Terminal 2 - API Server** (serves dashboard and API endpoints):
```bash
./start_backend.sh
# or
python3 backend/app.py
```

**Open Dashboard:**
- Navigate to `http://localhost:5001` in your browser
- Dashboard auto-refreshes every 5 seconds

---

## 📡 API Endpoints

### Health & Status
- `GET /api/health` - Health check
- `GET /api/stats` - Summary statistics

### Analytics
- `GET /api/analytics` - Full analytics data
- `GET /api/conversations` - All conversation histories
- `GET /api/conversations/<chat_id>` - Specific conversation

### Series Integration
- `GET /api/users/<user_id>/connections` - Get user connections from Series API

### Contacts
- `GET /api/contacts` - Get all contacts (requires permission)
- `GET /api/contacts/<phone>` - Get contact by phone (requires permission)
- `GET /api/contacts/search?q=<query>` - Search contacts (requires permission)
- `GET /api/contacts/category/<category>` - Get contacts by category (requires permission)
- `POST /api/contacts/sync` - Sync contacts from macOS (requires permission)

### Conversations
- `GET /api/conversations/<chat_id>/thread` - Get conversation thread
- `GET /api/conversations/<chat_id>/summary` - Get conversation summary
- `GET /api/conversations/<chat_id>/next_message` - Generate next message
- `GET /api/conversations/<chat_id>/state` - Get conversation state

### Multi-Agent System
- `POST /api/agents/process` - Process user request (order, book, call, etc.)
- `POST /api/agents/match_contact` - Match request to contact
- `POST /api/agents/suggestions` - Get action suggestions

### Permissions
- `GET /api/permissions` - Get permission status
- `POST /api/permissions/grant` - Grant contact permission
- `POST /api/permissions/deny` - Deny contact permission

---

## 💡 Usage Examples

### Basic Messaging
Send a message to your configured `SENDER_NUMBER` and the bot will:
- Detect the language
- Analyze sentiment and intent
- Generate an AI-powered response
- Respond in the detected language

### Contact-Based Actions
```
User: "Order pizza"
Bot: "✅ I found 'Pizza Guy' in your contacts. Should I proceed with order? (Reply 'yes' to continue)"
User: "Yes"
Bot: "What would you like to order?"
User: "2 large margherita pizzas"
Bot: "✅ Order sent to Pizza Guy! 📨 Message sent: [order details]"
```

### Meeting Queries
```
User: "Any meetings for me?"
Bot: "📅 You have 3 upcoming meeting(s):
1. Team Standup - Tomorrow at 10:00 AM
2. Client Call - Dec 10 at 2:00 PM
3. Project Review - Dec 12 at 11:00 AM"
```

### Email Queries
```
User: "Any urgent emails?"
Bot: "📧 Found 2 urgent emails:
1. Payment Reminder - From: billing@company.com
2. Project Deadline - From: manager@company.com"
```

---

## 🎨 Dashboard Features

The web dashboard (`http://localhost:5001`) displays:

- **📊 Statistics Cards**:
  - Total Messages
  - Total Responses
  - Positive Sentiment
  - Active Conversations
- **📈 Charts**:
  - Sentiment Distribution
  - Language Distribution
  - Intent Analysis
- **📋 Recent Activity**:
  - Top 5 most recent conversations
  - Chat ID, Language, Message Count
- **⚡ Real-Time Updates**:
  - Auto-refreshes every 5 seconds
  - Live statistics

---

## 🔒 Security & Privacy

- **Permission System** - All contact access requires explicit user permission
- **Input Sanitization** - All user inputs are sanitized
- **Content Moderation** - AI-powered content filtering
- **Rate Limiting** - Prevents API abuse
- **Error Handling** - Graceful error handling without exposing sensitive data
- **Environment Variables** - All secrets stored in `.env` (not committed to git)

---

## 🧪 Testing

To verify everything is working:

1. **Start the services**:
   ```bash
   ./start_all.sh
   ```

2. **Send a test message** to your `SENDER_NUMBER`

3. **Check the dashboard** at `http://localhost:5001`

4. **Verify analytics** are updating in real-time

---

## 🏗️ Architecture

### Backend Services

- **Bot Service** (`backend/bot_service.py`):
  - Consumes messages from Kafka (Series events)
  - Processes messages through AI pipeline
  - Sends responses via Series API
  - Manages contacts, conversations, and actions

- **API Server** (`backend/app.py`):
  - Flask REST API for dashboard data
  - Serves frontend dashboard
  - Provides API endpoints for all features

### Data Flow

1. **Message Received** → Kafka event → Bot Service
2. **Processing** → Language detection → Sentiment analysis → AI response generation
3. **Response** → Series API → iMessage sent
4. **Analytics** → File persistence → Dashboard updates

### Integration Points

- **Series API** - Core messaging platform
- **Kafka** - Event streaming
- **OpenAI** - AI/LLM capabilities
- **Gmail API** - Email and calendar access
- **Google Calendar API** - Meeting information
- **macOS Contacts/Calendar** - Native macOS integration

---

## 📝 License

This project is built for hackathon purposes.

---

## 🙏 Acknowledgments

- **Series Platform** - For providing the iMessage Service API
- **OpenAI** - For GPT-4o-mini API
- **Google** - For Gmail and Calendar APIs

---

## 📞 Support

For questions or issues:
- 📧 Email: amruthakravishankar@outlook.com; venkateshsneha30@gmail.com
- 💻 GitHub: [harithsya24/ping-human](https://github.com/harithsya24/ping-human)
