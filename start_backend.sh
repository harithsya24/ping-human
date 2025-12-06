#!/bin/bash
# Start the backend API server
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || true
python3 backend/app.py

