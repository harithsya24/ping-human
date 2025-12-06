# Quick Start Guide

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

Or if using conda base environment:
```bash
conda install -c conda-forge flask flask-cors
pip install -r requirements.txt
```

## Step 2: Set Up Environment

Make sure you have a `.env` file (copy from `env.example` if needed):
```bash
cp env.example .env
```

## Step 3: Run the Application

You need **3 terminals** (or use the scripts):

### Option A: Using Scripts (Easiest)

**Terminal 1 - Start Bot Service:**
```bash
./start_bot.sh
```

**Terminal 2 - Start API Server:**
```bash
./start_backend.sh
```

**Terminal 3 - View Dashboard:**
Open `frontend/index.html` in your web browser (double-click the file)

### Option B: Manual Commands

**Terminal 1 - Bot Service** (processes messages):
```bash
python backend/bot_service.py
```

**Terminal 2 - API Server** (serves dashboard data):
```bash
python backend/app.py
```

**Terminal 3 - View Dashboard:**
- Open `frontend/index.html` in your browser, OR
- Serve it with: `cd frontend && python -m http.server 8000`
- Then open: `http://localhost:8000`

## What You'll See

1. **Bot Service Terminal**: Shows Kafka connection and message processing
2. **API Server Terminal**: Shows Flask server running on port 5000
3. **Dashboard**: Beautiful web interface showing real-time analytics

## Testing

1. Send a message to `+16463769330` from another phone
2. Watch the bot service terminal process it
3. See the dashboard update automatically!

## Troubleshooting

- **ModuleNotFoundError**: Make sure dependencies are installed
- **Port 5000 in use**: Change `API_PORT` in `.env` or stop other services
- **Dashboard not loading**: Make sure API server is running on port 5000

