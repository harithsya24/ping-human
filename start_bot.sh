#!/bin/bash
# Start the bot service (Kafka consumer)
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || true
python3 backend/bot_service.py

