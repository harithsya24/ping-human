#!/bin/bash
# Start backend server and open the PingHumans frontend dashboard in browser

cd "$(dirname "$0")"

# Check if backend is already running
if curl -s http://localhost:5001/api/health > /dev/null 2>&1; then
    echo "✅ Backend server is already running"
else
    echo "🚀 Starting backend server..."
    source .venv/bin/activate 2>/dev/null || true
    # Start backend in background
    nohup python3 backend/app.py > backend.log 2>&1 &
    BACKEND_PID=$!
    echo "Backend server started (PID: $BACKEND_PID)"
    echo "Waiting for server to start..."
    sleep 3
fi

# Open frontend in browser
echo "🌐 Opening frontend dashboard..."
open http://localhost:5001

echo "✅ Frontend should now be open in your browser!"
echo "📝 Backend logs: tail -f backend.log"

