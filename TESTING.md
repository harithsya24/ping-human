# Testing Guide - How to Verify Everything Works

## Quick Start Testing

### 1. Start the Services

**Terminal 1 - Backend API:**
```bash
python backend/app.py
```
You should see:
```
[API] Starting server on http://localhost:5001
```

**Terminal 2 - Bot Service:**
```bash
python backend/bot_service.py
```
You should see:
```
[Bot] Starting PingHumans bot service...
[Bot] Connected to Kafka, waiting for messages...
[Bot] Ready! Send a message to +16463769330 to test.
```

### 2. Run Automated Tests

**Terminal 3 - Run Test Suite:**
```bash
python test_features.py
```

This will test:
- ✅ API health
- ✅ Contact management endpoints
- ✅ Conversation tracking
- ✅ Next message generation
- ✅ Decision support
- ✅ Stats endpoint

## Manual Testing Steps

### Test 1: API Health Check

```bash
curl http://localhost:5001/api/health
```

Expected response:
```json
{"status": "ok", "service": "PingHumans API"}
```

### Test 2: Send a Test Message

1. Send a message to **+16463769330** from your phone
2. Watch the bot service terminal - you should see:
   ```
   [Bot] New message in chat <chat_id> from <phone>: <your message>
   [Bot] Analysis - Language: English (en), Sentiment: positive, Intent: greeting
   [Bot] 📨 User <name> has replied within the last hour
   [Bot] Conversation state: send_reply (priority: high)
   [Bot] ✅ Sent AI reply: <response>
   [Bot] 📊 Conversation summary: 2 messages, 1 participants
   ```

### Test 3: Check Contact Management

```bash
# Get all contacts
curl http://localhost:5001/api/contacts

# Get contact by phone (replace with actual phone)
curl http://localhost:5001/api/contacts/+1234567890

# Search contacts
curl "http://localhost:5001/api/contacts/search?q=John"
```

### Test 4: Check Conversation Threads

```bash
# Get all conversations
curl http://localhost:5001/api/conversations

# Get specific conversation thread (replace with actual chat_id)
curl http://localhost:5001/api/conversations/123/thread

# Get conversation summary
curl http://localhost:5001/api/conversations/123/summary

# Check if user replied
curl "http://localhost:5001/api/conversations/123/has_replied?sender=+1234567890&within_minutes=60"

# Get pending replies
curl http://localhost:5001/api/conversations/pending
```

### Test 5: Test Next Message Generation

```bash
# Get next message suggestion (replace chat_id)
curl "http://localhost:5001/api/conversations/123/next_message?contact_name=John"

# Generate follow-up message
curl -X POST http://localhost:5001/api/conversations/123/follow_up \
  -H "Content-Type: application/json" \
  -d '{"last_message": "Hello, how are you?", "contact_name": "John"}'

# Get multiple message options
curl -X POST http://localhost:5001/api/conversations/123/message_options \
  -H "Content-Type: application/json" \
  -d '{"scenario": "User asked about pricing", "contact_name": "John"}'
```

### Test 6: Test Decision Support

```bash
# Get conversation state
curl http://localhost:5001/api/conversations/123/state

# Check if should send message
curl http://localhost:5001/api/conversations/123/should_send

# Get decision support
curl -X POST http://localhost:5001/api/conversations/123/decision_support \
  -H "Content-Type: application/json" \
  -d '{"question": "Should I send a follow-up message?", "contact_name": "John"}'

# Get conversation insights
curl http://localhost:5001/api/conversations/123/insights
```

### Test 7: Check Dashboard

1. Open browser: `http://localhost:5001`
2. You should see:
   - Real-time stats updating
   - Conversation counts
   - Sentiment distribution
   - Top languages
   - Active conversations

## Verification Checklist

### ✅ Contact Management
- [ ] Contacts are fetched from Series API
- [ ] Contact names are displayed instead of phone numbers
- [ ] Contact search works
- [ ] Contact info is cached

### ✅ Conversation Tracking
- [ ] Messages are tracked in threads
- [ ] Conversation summaries are accurate
- [ ] Reply detection works
- [ ] Pending replies are identified

### ✅ Reply Detection
- [ ] System detects when user replies
- [ ] Time windows work correctly
- [ ] Multiple conversations tracked separately

### ✅ Next Message Generation
- [ ] AI generates context-aware messages
- [ ] Follow-up messages are relevant
- [ ] Multiple options are provided
- [ ] Language preferences are respected

### ✅ Decision Support
- [ ] Conversation state is analyzed
- [ ] Recommendations are provided
- [ ] Send/don't send decisions are accurate
- [ ] Insights are generated

### ✅ Bot Service Integration
- [ ] Bot tracks messages automatically
- [ ] Contact names are shown in logs
- [ ] Reply detection works in real-time
- [ ] Conversation state is analyzed
- [ ] AI responses use full context

## Troubleshooting

### API Not Responding
- Check if backend is running: `python backend/app.py`
- Check port 5001 is not in use
- Check firewall settings

### Bot Service Not Receiving Messages
- Check Kafka connection
- Verify topic name in `.env`
- Check consumer group settings
- Look for connection errors in logs

### Contact Names Not Showing
- Contacts may need to be fetched first
- Check Series API connection
- Verify API key is correct
- Check contact cache

### AI Features Not Working
- Verify `OPENAI_API_KEY` is set in `.env`
- Check API key is valid
- Check rate limits on OpenAI account
- Look for error messages in logs

## Expected Behavior

### When You Send a Message:

1. **Bot Service Logs:**
   ```
   [Bot] New message in chat 123 from John Doe (+1234567890): Hello!
   [Bot] Analysis - Language: English (en), Sentiment: positive, Intent: greeting
   [Bot] 📨 User John Doe has replied within the last hour
   [Bot] Conversation state: send_reply (priority: high)
   [Bot] ✅ Sent AI reply: Hi John! How can I help you today?
   [Bot] 📊 Conversation summary: 2 messages, 1 participants
   ```

2. **API Response:**
   - Contact info is cached
   - Conversation thread is updated
   - Reply status is tracked
   - Next message suggestions are available

3. **Dashboard:**
   - Stats update automatically
   - New conversation appears
   - Message count increases

## Advanced Testing

### Test Multiple Conversations

1. Send messages from different phone numbers
2. Verify each conversation is tracked separately
3. Check contact names are different
4. Verify reply detection works per conversation

### Test Reply Detection

1. Send a message
2. Wait for bot response
3. Send another message (this should be detected as a reply)
4. Check logs for "has replied" message

### Test Decision Support

1. Send a message
2. Wait 30+ minutes
3. Check `/api/conversations/<chat_id>/should_send`
4. Should recommend sending a follow-up

## Success Indicators

✅ **Everything is working if:**
- API responds to all endpoints
- Bot service processes messages
- Contact names appear in logs
- Conversation threads are tracked
- Reply detection works
- AI generates relevant responses
- Dashboard shows real-time data

## Need Help?

If something isn't working:
1. Check the logs for error messages
2. Verify all environment variables are set
3. Ensure all services are running
4. Check network connectivity
5. Review the troubleshooting section above

