# What to Run - Quick Guide

## You need to run 2 things:

### 1. Bot Service (Terminal 1)
**What it does:** Processes incoming messages from Kafka, generates AI responses

```bash
python backend/bot_service.py
```

**What you'll see:**
- `[Bot] OpenAI client initialized`
- `[Bot] Connected to Kafka, waiting for messages...`
- `[Bot] Ready! Send a message to +16463769330 to test.`

---

### 2. API Server (Terminal 2)
**What it does:** Serves the dashboard and analytics data

```bash
python backend/app.py
```

**What you'll see:**
- `[API] Starting server on http://localhost:5001`
- ` * Running on http://0.0.0.0:5001`

---

### 3. View Dashboard
**Open in browser:**
- `http://localhost:5001` 
- OR `http://192.168.1.12:5001` (your IP)

The dashboard will load automatically!

---

## Quick Start Commands

**Option A: Use scripts**
```bash
# Terminal 1
./start_bot.sh

# Terminal 2  
./start_backend.sh

# Then open http://localhost:5001 in browser
```

**Option B: Manual**
```bash
# Terminal 1
python backend/bot_service.py

# Terminal 2
python backend/app.py

# Browser
Open http://localhost:5001
```

---

## That's it! 

Once both are running:
- ✅ Bot processes messages automatically
- ✅ Dashboard shows real-time analytics
- ✅ Send messages to `+16463769330` to test

---

## Troubleshooting

**Port 5001 in use?**
- Change `API_PORT` in `.env` file

**Module not found?**
- Run: `pip install -r requirements.txt`

**Dashboard not loading?**
- Make sure API server (Terminal 2) is running
- Check browser console for errors

