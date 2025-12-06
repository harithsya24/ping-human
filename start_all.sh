#!/bin/bash
# Start both bot service and API server
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || true

# Start bot service in background
python3 backend/bot_service.py &
BOT_PID=$!

# Start API server
python3 backend/app.py &
API_PID=$!

echo "Bot service PID: $BOT_PID"
echo "API server PID: $API_PID"
echo "Open http://localhost:5000/api/health to check API"
echo "Open frontend/index.html in browser for dashboard"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "kill $BOT_PID $API_PID; exit" INT
wait

