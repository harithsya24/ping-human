# Guardrails System

## Overview

The guardrails system provides content safety, abuse prevention, and moderation capabilities for the messaging bot.

## Features

### 1. Content Safety Checks

- **Pattern Detection**: Blocks spam, phishing, and malicious content patterns
- **Keyword Filtering**: Detects harmful and inappropriate keywords
- **AI Moderation**: Uses OpenAI's moderation API for advanced content filtering
- **Response Validation**: Validates AI-generated responses before sending

### 2. Rate Limiting

- **Per-Minute Limits**: Default 10 messages per minute per user
- **Per-Hour Limits**: Default 50 messages per hour per user
- **Automatic Tracking**: Tracks message frequency per user
- **Violation Recording**: Records rate limit violations

### 3. User Management

- **User Blocking**: Blocks users after multiple violations
- **Flagging System**: Flags users for manual review
- **Violation History**: Tracks all safety violations per user
- **Auto-Block**: Automatically blocks users after 3 flags or 5 violations in 24 hours

### 4. Input Sanitization

- **Null Byte Removal**: Prevents injection attacks
- **Length Limits**: Limits input to 5000 characters
- **Whitespace Normalization**: Cleans excessive whitespace

## API Endpoints

### Get Guardrail Statistics
```bash
GET /api/guardrails/stats
```

Returns:
```json
{
  "total_violations": 10,
  "flagged_users": 2,
  "active_flags": 3,
  "violation_types": {
    "unsafe_content": 5,
    "rate_limit_exceeded": 3
  },
  "rate_limited_users": 1
}
```

### Check User Status
```bash
GET /api/guardrails/users/<phone>/status
```

Returns:
```json
{
  "allowed": true,
  "blocked": false
}
```

### Flag a User
```bash
POST /api/guardrails/users/<phone>/flag
Content-Type: application/json

{
  "reason": "inappropriate_content",
  "severity": "medium"
}
```

### Unblock a User
```bash
POST /api/guardrails/users/<phone>/unblock
```

### Reset User Flags
```bash
POST /api/guardrails/users/<phone>/reset
```

### Get Violations
```bash
# Get all violations
GET /api/guardrails/violations

# Get violations for specific user
GET /api/guardrails/violations?phone=+1234567890
```

### Get Flagged Users
```bash
GET /api/guardrails/flagged
```

## Configuration

### Rate Limits

Default limits can be adjusted in `guardrails.py`:
- `max_messages_per_minute`: 10
- `max_messages_per_hour`: 50

### Content Filters

Blocked patterns and keywords can be customized in `guardrails.py`:
- `BLOCKED_PATTERNS`: Regex patterns for spam/phishing
- `HARMFUL_KEYWORDS`: Keywords indicating harmful content
- `INAPPROPRIATE_KEYWORDS`: Keywords indicating inappropriate content

## How It Works

### Message Processing Flow

1. **User sends message** → Bot receives it
2. **Check user status** → Is user blocked?
3. **Check rate limits** → Within limits?
4. **Sanitize input** → Clean the message
5. **Content safety check** → Safe content?
6. **Process message** → Generate response
7. **Validate response** → Safe response?
8. **Send response** → Deliver to user

### Violation Handling

- **First violation**: Recorded, user warned
- **Multiple violations**: User flagged
- **3 flags**: User auto-blocked
- **5 violations in 24h**: User auto-blocked

### Auto-Block Conditions

Users are automatically blocked if:
- 3 or more flags
- 5 or more violations in 24 hours
- Manual flag with high severity

## Integration

The guardrails are automatically integrated into:

1. **Bot Service** (`backend/bot_service.py`):
   - Checks every incoming message
   - Validates every outgoing response
   - Records violations automatically

2. **API Server** (`backend/app.py`):
   - Provides guardrail statistics
   - Allows manual user management
   - Exposes violation history

3. **Dashboard Stats**:
   - Guardrail stats included in `/api/stats`
   - Shows violation counts and flagged users

## Usage Examples

### Check if Content is Safe
```python
from guardrails import check_content_safety

result = check_content_safety("Hello, how are you?")
if result["safe"]:
    print("Content is safe")
else:
    print(f"Unsafe: {result['message']}")
```

### Check Rate Limits
```python
from guardrails import check_rate_limit, record_message

phone = "+1234567890"
allowed, reason = check_rate_limit(phone)
if allowed:
    record_message(phone)
    # Process message
else:
    print(f"Rate limited: {reason}")
```

### Flag a User
```python
from guardrails import flag_user

flag_user("+1234567890", "spam", "high")
```

### Get Guardrail Stats
```python
from guardrails import get_guardrail_stats

stats = get_guardrail_stats()
print(f"Total violations: {stats['total_violations']}")
print(f"Flagged users: {stats['flagged_users']}")
```

## Monitoring

### View Guardrail Stats in Dashboard

The dashboard now includes guardrail statistics in the stats endpoint. Check:
- Total violations
- Flagged users count
- Violation types breakdown

### Log Messages

The bot service logs guardrail actions:
- `🚫 Message blocked: <reason>`
- `🚫 Rate limit exceeded: <reason>`
- `🚫 Unsafe content: <reason>`
- `⚠️ User auto-blocked after N violations`

## Best Practices

1. **Regular Monitoring**: Check guardrail stats regularly
2. **Review Violations**: Periodically review violation history
3. **Adjust Limits**: Tune rate limits based on usage patterns
4. **Update Filters**: Keep content filters updated
5. **Manual Review**: Review flagged users before permanent blocking

## Future Enhancements

- Machine learning-based spam detection
- Customizable filter rules per user/group
- Integration with external moderation services
- Automated response to violations
- User appeal process
- Whitelist/blacklist management

