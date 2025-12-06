# Testing Guide for Contact Management & Follow-Up Features

## Feature 1: Restricted Contact Management (Order, Call, Send)

### How to Test:

1. **Start the bot service:**
   ```bash
   ./start_bot.sh
   # or
   python3 backend/bot_service.py
   ```

2. **Test Order Action:**
   - Send a message to your bot number: `"order pizza"`
   - The bot should find a contact matching "pizza" and ask for confirmation
   - Reply "yes" to confirm
   - Provide order details when asked
   - The bot will send the order message

   **Allowed keywords:** `order`, `buy`, `purchase`, `get me`
   - ✅ "order pizza" → Will trigger
   - ✅ "buy coffee" → Will trigger
   - ✅ "purchase burger" → Will trigger
   - ✅ "get me pizza" → Will trigger
   - ❌ "i want pizza" → Will NOT trigger (removed)
   - ❌ "i need coffee" → Will NOT trigger (removed)

3. **Test Call Action:**
   - Send: `"call doctor"`
   - The bot should find a contact matching "doctor" and provide call instructions

   **Allowed keywords:** `call`, `phone`, `ring`, `dial`
   - ✅ "call mom" → Will trigger
   - ✅ "phone my friend" → Will trigger
   - ❌ "contact doctor" → Will NOT trigger

4. **Test Send/Message Action:**
   - Send: `"send message to John"`
   - The bot should find "John" in contacts and send a message
   - **This will also trigger the follow-up feature!**

   **Allowed keywords:** `send`, `message`, `text`, `text message`, `send message`
   - ✅ "send message to friend" → Will trigger
   - ✅ "message mom" → Will trigger
   - ✅ "text my friend" → Will trigger
   - ❌ "email friend" → Will NOT trigger

## Feature 2: Follow-Up Message Scheduler

### How It Works:
- When you send a message to a friend using the "send" action
- System waits 3 minutes for a reply
- If no reply within 3 minutes, schedules a follow-up for 2 hours later
- If reply is received, follow-up is automatically canceled

### How to Test:

1. **Send a message to a friend:**
   ```
   User: "send message to [friend's name]"
   Bot: "✅ I found '[friend's name]' in your contacts. Should I proceed with message? (Reply 'yes' to continue)"
   User: "yes"
   Bot: "📝 Please provide details for your message request:"
   User: "Hey, just checking in!"
   Bot: "✅ Message sent to [friend's name]!"
   ```

2. **Check the logs:**
   You should see in the bot console:
   ```
   [FollowUpScheduler] 📝 Tracking message to [friend's name] ([phone])
   [FollowUpScheduler] ⏰ Will check for reply at [time + 3 minutes]
   [FollowUpScheduler] 📅 Follow-up scheduled for [time + 2 hours]
   ```

3. **Test Reply Detection (Cancel Follow-Up):**
   - If your friend replies within 3 minutes, you should see:
   ```
   [Bot] ✅ Reply received - follow-up canceled
   [FollowUpScheduler] ✅ Reply received from [friend's name]!
   [FollowUpScheduler] 🚫 Canceling follow-up for chat [chat_id]
   ```

4. **Test Follow-Up Sending (No Reply):**
   - Wait 3 minutes (or modify `REPLY_WAIT_MINUTES` in `follow_up_scheduler.py` for faster testing)
   - Wait 2 hours total (or modify `FOLLOW_UP_DELAY_HOURS` for faster testing)
   - System will automatically send:
   ```
   "Hey [friend's name], just following up on my previous message. Let me know if you got a chance to see it!"
   ```

### Quick Testing (Modify Timeouts):

For faster testing, you can temporarily modify the delays in `backend/follow_up_scheduler.py`:

```python
REPLY_WAIT_MINUTES = 1  # Change from 3 to 1 minute for testing
FOLLOW_UP_DELAY_HOURS = 0.1  # Change from 2 hours to 6 minutes (0.1 hours) for testing
```

Then restart the bot service.

## Monitoring

### Check Follow-Up Status:
- Check `follow_up_data.json` file to see tracked messages and scheduled follow-ups
- Watch bot console logs for follow-up scheduler activity

### Expected Log Messages:

**When message is sent:**
```
[ActionExecutor] 📝 Message tracked for follow-up scheduling
[FollowUpScheduler] 📝 Tracking message to [name] ([phone])
[FollowUpScheduler] ⏰ Will check for reply at [time]
[FollowUpScheduler] 📅 Follow-up scheduled for [time]
```

**When reply received:**
```
[Bot] ✅ Reply received - follow-up canceled
[FollowUpScheduler] ✅ Reply received from [name]!
[FollowUpScheduler] 🚫 Canceling follow-up for chat [chat_id]
```

**When follow-up is sent:**
```
[FollowUpScheduler] ✅ Follow-up sent to [name] ([phone])
[Bot] 📨 Follow-up sent to [phone]: Hey [name], just following up...
```

## Troubleshooting

1. **Follow-up not working?**
   - Check if `follow_up_scheduler.py` is imported correctly
   - Verify the scheduler started: Look for `[Bot] ✅ Follow-up scheduler started`
   - Check `follow_up_data.json` exists and has data

2. **Contact actions not triggering?**
   - Make sure you're using the exact keywords: `order`, `call`, `send`, `message`, `text`
   - Check bot logs for: `[Bot] 🤖 Detected actionable request`

3. **No contact found?**
   - Make sure the contact exists in your contacts
   - Try syncing contacts: The bot syncs from macOS Contacts on startup
   - Check bot logs for contact matching attempts

## Notes

- The follow-up scheduler runs in a background thread and checks every 30 seconds
- Data is persisted to `follow_up_data.json` (automatically created)
- Follow-ups are only scheduled for messages sent via the "send" action
- The system automatically cancels follow-ups if a reply is detected

