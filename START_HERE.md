# 🚀 START HERE - Quick Commands

## Start the Services

### **Easiest Way - Use Scripts:**

**Open Terminal 1:**
```bash
cd /Users/amruthakanakatteravishankar/Desktop/ping-human
./start_backend.sh
```

**Open Terminal 2 (new terminal window):**
```bash
cd /Users/amruthakanakatteravishankar/Desktop/ping-human
./start_bot.sh
```

---

### **Alternative - Direct Commands:**

**Terminal 1 - Backend API:**
```bash
cd /Users/amruthakanakatteravishankar/Desktop/ping-human
source .venv/bin/activate
python3 backend/app.py
```

**Terminal 2 - Bot Service:**
```bash
cd /Users/amruthakanakatteravishankar/Desktop/ping-human
source .venv/bin/activate
python3 backend/bot_service.py
```

---

## ✅ Verify It's Working

**Test Backend:**
```bash
curl http://localhost:5001/api/health
```

Should return: `{"status": "ok", "service": "PingHumans API"}`

**Open Dashboard:**
Open browser: `http://localhost:5001`

**Send Test Message:**
Send a message to `+16463769330` and watch Terminal 2 for activity.

---

## ⚠️ Common Issues

### "python: command not found"
→ Use `python3` instead

### "Permission denied" on scripts
→ Run: `chmod +x start*.sh`

### "Port 5001 already in use"
→ Kill it: `lsof -ti:5001 | xargs kill -9`

### "Module not found"
→ Install: `pip3 install -r requirements.txt`

---

## 📝 What Each Service Does

- **Backend API** (`backend/app.py`): Serves the dashboard and API endpoints
- **Bot Service** (`backend/bot_service.py`): Processes messages from Kafka and responds

Both need to be running for the system to work!

