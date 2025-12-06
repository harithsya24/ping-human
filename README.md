# PingHumans

AI-powered messaging bot with sentiment analysis, intent detection, multilingual support, and proactive messaging.

## 👤 Author

**Amrutha Kanakatte Ravishankar, Sneha Venkatesh**
- 📧 Email: amruthakravishankar@outlook.com; venkateshsneha30@gmail.com
- 💻 GitHub: [Your GitHub](https://github.com/harithsya24)

## Project Structure

```
ping-human/
├── backend/              # Backend services
│   ├── app.py           # Flask API server
│   └── bot_service.py   # Kafka consumer & message processing
├── frontend/            # Frontend dashboard
│   └── index.html       # Web dashboard UI
├── main.py              # (Legacy - use backend/bot_service.py instead)
├── kafka_consumer.py    # Kafka consumer module
├── series_api.py        # Series API client
├── sentiment_analyzer.py # Sentiment & intent analysis
├── language_detector.py # Language detection
├── ai_responder.py      # AI response generation
├── analytics.py         # Analytics tracking
├── proactive_messenger.py # Proactive messaging
└── requirements.txt     # Python dependencies
```

## Features

- 🌍 **Multilingual Support** - Automatically detects language and responds in the user's language
- 🤖 **LLM-Powered Responses** - Intelligent, context-aware replies using OpenAI GPT-4o-mini
- 📊 **Real-Time Analytics Dashboard** - Web UI to view stats, sentiment, languages, and conversations
- 🎯 **Sentiment & Intent Detection** - Analyzes messages for sentiment and intent
- 💬 **Conversation Summarization** - AI-generated conversation summaries
- ⚡ **Proactive Messaging** - Automatically checks in with users after inactivity
- 🧠 **Context Memory** - Maintains conversation history per chat
- 🔄 **Auto-Reconnect** - Automatically reconnects if Kafka connection is lost

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from `env.example`:
```bash
cp env.example .env
```

3. (Optional) Add API port to `.env`:
```
API_PORT=5000
FLASK_DEBUG=False
```

## Running the Application

### Option 1: Run Everything Together
```bash
./start_all.sh
```

### Option 2: Run Separately

**Terminal 1 - Bot Service** (processes messages):
```bash
./start_bot.sh
# or
python backend/bot_service.py
```

**Terminal 2 - API Server** (serves dashboard data):
```bash
./start_backend.sh
# or
python backend/app.py
```

**Terminal 3 - Open Dashboard**:
Open `frontend/index.html` in your web browser, or serve it:
```bash
# Using Python's HTTP server
cd frontend && python -m http.server 8000
# Then open http://localhost:8000
```

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/stats` - Summary statistics
- `GET /api/analytics` - Full analytics data
- `GET /api/conversations` - All conversation histories
- `GET /api/conversations/<chat_id>` - Specific conversation
- `GET /api/users/<user_id>/connections` - Get user connections from Series API

## Dashboard Features

The web dashboard (`frontend/index.html`) shows:
- Real-time message and response counts
- Sentiment distribution
- Top languages detected
- Top intents
- Active conversations
- Auto-refreshes every 5 seconds

## Architecture

### Backend
- **Bot Service** (`backend/bot_service.py`): Kafka consumer that processes incoming messages
- **API Server** (`backend/app.py`): Flask REST API for dashboard data

### Frontend
- **Dashboard** (`frontend/index.html`): Single-page web app with real-time analytics

### Modules
- Each functionality is in its own module for maintainability
- Shared state (analytics, conversations) is accessible by both services

## Usage

1. Start the bot service and API server
2. Send messages to `+16463769330`
3. View analytics in the dashboard at `http://localhost:5001`
4. The dashboard auto-refreshes to show latest stats

## Testing

To verify everything is working:

```bash
# Run automated tests
python test_features.py
```

See [TESTING.md](TESTING.md) for detailed testing instructions and verification steps.

## Demo Features

Perfect for hackathon demo:
- ✅ Human-centered impact (smart, helpful AI assistant)
- ✅ Technical execution (real-time Kafka + LLM + REST API)
- ✅ Creativity (sentiment analysis, proactive messaging, multilingual)
- ✅ Demo quality (beautiful dashboard, smart responses)
- ✅ Clean architecture (separated backend/frontend)
