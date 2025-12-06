"""Gmail API client for reading emails and detecting meetings/urgent messages."""
import os
import base64
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re

load_dotenv()

# Gmail API configuration
# Store credentials in project root (parent directory)
_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", os.path.join(_root_dir, "credentials.json"))
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", os.path.join(_root_dir, "token.json"))
GMAIL_USER = os.getenv("EMAIL_USERNAME", "")

# Try to import Google API libraries
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    print("[Gmail] Google API libraries not installed. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def get_gmail_service():
    """Get authenticated Gmail service."""
    if not GMAIL_AVAILABLE:
        return None
    
    creds = None
    
    # Load existing token
    if os.path.exists(GMAIL_TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"[Gmail] Error loading token: {e}")
    
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[Gmail] Error refreshing token: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(GMAIL_CREDENTIALS_FILE):
                print(f"[Gmail] Credentials file not found: {GMAIL_CREDENTIALS_FILE}")
                print("[Gmail] Please download credentials.json from Google Cloud Console")
                return None
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"[Gmail] Error getting credentials: {e}")
                return None
        
        # Save credentials for next run
        try:
            with open(GMAIL_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"[Gmail] Error saving token: {e}")
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f"[Gmail] Error building service: {e}")
        return None

def get_calendar_service():
    """Get authenticated Calendar service."""
    if not GMAIL_AVAILABLE:
        return None
    
    creds = None
    
    # Load existing token
    if os.path.exists(GMAIL_TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"[Gmail] Error loading token: {e}")
    
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[Gmail] Error refreshing token: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(GMAIL_CREDENTIALS_FILE):
                return None
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"[Gmail] Error getting credentials: {e}")
                return None
        
        # Save credentials for next run
        try:
            with open(GMAIL_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"[Gmail] Error saving token: {e}")
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"[Gmail] Error building calendar service: {e}")
        return None

def decode_message_body(message):
    """Decode email message body."""
    body = ""
    if 'payload' in message:
        payload = message['payload']
        parts = payload.get('parts', [])
        
        for part in parts:
            if part['mimeType'] == 'text/plain':
                data = part['body']['data']
                body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif part['mimeType'] == 'text/html':
                data = part['body']['data']
                body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        # If no parts, try body directly
        if not body and 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
    
    return body

def get_recent_emails(service, max_results=10, query=""):
    """Get recent emails from Gmail."""
    if not service:
        return []
    
    try:
        results = service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q=query
        ).execute()
        
        messages = results.get('messages', [])
        email_list = []
        
        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                headers = message['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                body = decode_message_body(message)
                
                email_list.append({
                    'id': msg['id'],
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'body': body,
                    'snippet': message.get('snippet', '')
                })
            except Exception as e:
                print(f"[Gmail] Error getting message {msg.get('id')}: {e}")
                continue
        
        return email_list
    except HttpError as e:
        print(f"[Gmail] Error getting emails: {e}")
        return []

def detect_urgent_emails(emails: List[Dict], ai_client=None, max_urgent: int = 3) -> List[Dict]:
    """
    Detect urgent emails using ML classification to avoid false positives.
    Only returns the most urgent emails (limited to max_urgent).
    """
    if not emails:
        return []
    
    # First pass: filter out obvious non-urgent emails (marketing, spam, etc.)
    filtered_emails = []
    spam_indicators = [
        'unsubscribe', 'marketing', 'promotion', 'sale', 'discount', 'offer',
        'newsletter', 'advertisement', 'shopping', 'retail', 'store',
        'macy', 'michael kors', 'monster', 'job alert', 'career', 'hiring'
    ]
    
    for email in emails:
        text = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
        sender = email.get('from', '').lower()
        
        # Skip obvious marketing/spam
        is_spam = any(indicator in text or indicator in sender for indicator in spam_indicators)
        if is_spam:
            continue
        
        filtered_emails.append(email)
    
    if not filtered_emails:
        return []
    
    # Second pass: Use AI to classify urgency if available
    if ai_client:
        try:
            urgent_emails = _classify_urgent_emails_ai(filtered_emails, ai_client, max_urgent)
            return urgent_emails
        except Exception as e:
            print(f"[Gmail] AI classification error: {e}, falling back to keyword matching")
    
    # Fallback: simple keyword matching (limited)
    urgent_keywords = [
        'urgent', 'asap', 'emergency', 'critical', 'deadline today',
        'action required immediately', 'response needed today'
    ]
    
    urgent_emails = []
    for email in filtered_emails[:10]:  # Limit to 10 for processing
        text = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
        
        # More strict keyword matching
        is_urgent = any(keyword in text for keyword in urgent_keywords)
        
        # Check for multiple exclamation marks (but less weight)
        if email.get('subject', '').count('!') >= 3:
            is_urgent = True
        
        if is_urgent:
            urgent_emails.append({
                **email,
                'urgency_score': 0.7,  # Default score
                'urgency_reason': 'Contains urgent keywords'
            })
    
    # Return only top max_urgent
    return urgent_emails[:max_urgent]

def _classify_urgent_emails_ai(emails: List[Dict], ai_client, max_urgent: int = 3) -> List[Dict]:
    """Use AI to classify email urgency and return only truly urgent ones."""
    from openai import OpenAI
    
    if not isinstance(ai_client, OpenAI):
        raise ValueError("Invalid AI client")
    
    # Prepare email summaries for AI
    email_summaries = []
    for i, email in enumerate(emails[:20]):  # Limit to 20 for AI processing
        summary = {
            'index': i,
            'subject': email.get('subject', '')[:100],
            'from': email.get('from', '')[:50],
            'snippet': email.get('snippet', '')[:200]
        }
        email_summaries.append(summary)
    
    # Create prompt for AI classification
    prompt = f"""Analyze these emails and identify ONLY truly urgent ones (not marketing, spam, or promotional).

URGENT emails are:
- Work-related deadlines or action items
- Personal emergencies or time-sensitive requests
- Important notifications requiring immediate attention
- Time-sensitive business communications

NOT URGENT (ignore these):
- Marketing emails, promotions, sales
- Job alerts, career opportunities
- Newsletters, subscriptions
- Shopping, retail, advertisements
- Social notifications, updates

Emails to analyze:
"""
    for email in email_summaries:
        prompt += f"\n{email['index']}. From: {email['from']}\n   Subject: {email['subject']}\n   Preview: {email['snippet']}\n"
    
    prompt += f"\nReturn JSON with only the indices of truly urgent emails (max {max_urgent}):\n"
    prompt += '{"urgent_indices": [0, 2, 5], "reasoning": "brief explanation"}'
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an email urgency classifier. Analyze emails and identify only truly urgent ones, ignoring marketing/spam."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        urgent_indices = result.get('urgent_indices', [])
        
        # Get urgent emails based on AI classification
        urgent_emails = []
        for idx in urgent_indices[:max_urgent]:
            if 0 <= idx < len(emails):
                urgent_emails.append({
                    **emails[idx],
                    'urgency_score': 0.9,  # High score for AI-classified
                    'urgency_reason': result.get('reasoning', 'AI classified as urgent')
                })
        
        print(f"[Gmail] AI classified {len(urgent_emails)} urgent emails out of {len(emails)}")
        return urgent_emails
    
    except Exception as e:
        print(f"[Gmail] Error in AI classification: {e}")
        raise

def extract_meeting_info(email: Dict) -> Optional[Dict]:
    """Extract meeting information from email."""
    subject = email.get('subject', '')
    body = email.get('body', '')
    text = subject + ' ' + body
    
    # Patterns for meeting detection
    meeting_patterns = [
        r'meeting\s+(?:on|at|for)\s+([^\.\n]+)',
        r'call\s+(?:on|at|for)\s+([^\.\n]+)',
        r'appointment\s+(?:on|at|for)\s+([^\.\n]+)',
        r'conference\s+(?:on|at|for)\s+([^\.\n]+)',
    ]
    
    # Date/time patterns
    date_patterns = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY
        r'(\w+\s+\d{1,2},?\s+\d{4})',  # January 15, 2024
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',  # Time
    ]
    
    # Extract meeting title
    meeting_title = subject
    for pattern in meeting_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            meeting_title = match.group(1).strip()
            break
    
    # Extract dates/times
    dates = []
    times = []
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)
    
    # Try to parse datetime
    meeting_datetime = None
    if dates:
        # Simple parsing - can be enhanced
        try:
            # Try to parse first date found
            date_str = dates[0]
            # This is simplified - would need proper date parsing
            meeting_datetime = date_str
        except:
            pass
    
    if meeting_title or dates:
        return {
            'title': meeting_title,
            'datetime': meeting_datetime,
            'dates': dates,
            'email_id': email.get('id'),
            'email_subject': subject,
            'email_from': email.get('from', '')
        }
    
    return None

def get_upcoming_meetings(service, days_ahead=7):
    """Get upcoming meetings from Google Calendar."""
    if not service:
        return []
    
    try:
        now = datetime.utcnow().isoformat() + 'Z'
        later = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            timeMax=later,
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        meetings = []
        
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            meetings.append({
                'id': event.get('id'),
                'title': event.get('summary', 'No Title'),
                'description': event.get('description', ''),
                'start': start,
                'end': end,
                'location': event.get('location', ''),
                'attendees': [a.get('email') for a in event.get('attendees', [])],
                'organizer': event.get('organizer', {}).get('email', '')
            })
        
        return meetings
    except HttpError as e:
        print(f"[Gmail] Error getting calendar events: {e}")
        return []

def check_gmail_setup():
    """Check if Gmail API is properly configured."""
    if not GMAIL_AVAILABLE:
        return {
            "configured": False,
            "message": "Google API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        }
    
    if not os.path.exists(GMAIL_CREDENTIALS_FILE):
        return {
            "configured": False,
            "message": f"Credentials file not found: {GMAIL_CREDENTIALS_FILE}. Please download from Google Cloud Console."
        }
    
    service = get_gmail_service()
    if not service:
        return {
            "configured": False,
            "message": "Failed to authenticate with Gmail API. Please check credentials."
        }
    
    return {
        "configured": True,
        "message": "Gmail API is configured and ready"
    }

