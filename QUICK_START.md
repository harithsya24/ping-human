# Quick Start Guide

## Running the Services

### Option 1: Use the Start Scripts (Recommended)

**Start Backend API:**
```bash
./start_backend.sh
```

**Start Bot Service:**
```bash
./start_bot.sh
```

**Start Both:**
```bash
./start_all.sh
```

### Option 2: Manual Start

**If `python` command doesn't work, use `python3`:**

**Terminal 1 - Backend API:**
```bash
cd /Users/amruthakanakatteravishankar/Desktop/ping-human
python3 backend/app.py
```

**Terminal 2 - Bot Service:**
```bash
cd /Users/amruthakanakatteravishankar/Desktop/ping-human
python3 backend/bot_service.py
```

### Option 3: With Virtual Environment

If you have a virtual environment:

```bash
# Activate virtual environment
source .venv/bin/activate  # or: source venv/bin/activate

# Then run
python backend/app.py
python backend/bot_service.py
```

## Verify It's Working

1. **Check Backend API:**
   ```bash
   curl http://localhost:5001/api/health
   ```
   Should return: `{"status": "ok", "service": "PingHumans API"}`

2. **Open Dashboard:**
   Open browser: `http://localhost:5001`

3. **Send Test Message:**
   Send a message to `+16463769330` and watch the bot service terminal for activity.

## Troubleshooting

### "python: command not found"
- Use `python3` instead of `python`
- Or create an alias: `alias python=python3`

### "Module not found"
- Install dependencies: `pip3 install -r requirements.txt`
- Or activate virtual environment first

### "Port 5001 already in use"
- Kill the process: `lsof -ti:5001 | xargs kill -9`
- Or change port in `.env`: `API_PORT=5002`

