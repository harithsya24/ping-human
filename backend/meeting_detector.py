"""Detect meetings from emails and calendar, and extract meeting details."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import re
from gmail_client import get_gmail_service, get_calendar_service, get_recent_emails, get_upcoming_meetings, extract_meeting_info
from icalendar_client import get_upcoming_icalendar_meetings

def parse_datetime(date_str: str) -> Optional[datetime]:
    """Parse various date/time formats."""
    if not date_str:
        return None
    
    # Common formats
    formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y %H:%M',
        '%m-%d-%Y %H:%M',
        '%B %d, %Y %H:%M',
        '%b %d, %Y %H:%M',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    
    return None

def get_all_meetings(days_ahead=7) -> List[Dict]:
    """Get all meetings from Google Calendar, iCalendar, and emails."""
    meetings = []
    meeting_ids = set()  # Track to avoid duplicates
    
    # Get from Google Calendar
    calendar_service = get_calendar_service()
    if calendar_service:
        calendar_meetings = get_upcoming_meetings(calendar_service, days_ahead)
        for meeting in calendar_meetings:
            start_str = meeting.get('start', '')
            start_dt = parse_datetime(start_str)
            meeting_id = meeting.get('id')
            
            if meeting_id not in meeting_ids:
                meetings.append({
                    'id': meeting_id,
                    'title': meeting.get('title', 'No Title'),
                    'description': meeting.get('description', ''),
                    'start': start_dt,
                    'start_str': start_str,
                    'end': meeting.get('end', ''),
                    'location': meeting.get('location', ''),
                    'source': 'google_calendar',
                    'attendees': meeting.get('attendees', []),
                    'organizer': meeting.get('organizer', '')
                })
                meeting_ids.add(meeting_id)
    
    # Get from macOS Calendar (iCalendar)
    try:
        icalendar_meetings = get_upcoming_icalendar_meetings(days_ahead)
        for meeting in icalendar_meetings:
            meeting_id = meeting.get('id')
            
            # Skip if already added from Google Calendar (duplicate check)
            if meeting_id not in meeting_ids:
                meetings.append({
                    'id': meeting_id,
                    'title': meeting.get('title', 'No Title'),
                    'description': meeting.get('description', ''),
                    'start': meeting.get('start'),
                    'start_str': meeting.get('start_str', ''),
                    'end': meeting.get('end'),
                    'end_str': meeting.get('end_str', ''),
                    'location': meeting.get('location', ''),
                    'source': 'icalendar',
                    'attendees': meeting.get('attendees', []),
                    'calendar': meeting.get('calendar', '')
                })
                meeting_ids.add(meeting_id)
    except Exception as e:
        print(f"[MeetingDetector] Error getting iCalendar events: {e}")
    
    # Get from Gmail (recent emails with meeting info)
    gmail_service = get_gmail_service()
    if gmail_service:
        recent_emails = get_recent_emails(gmail_service, max_results=20, query="meeting OR call OR appointment OR conference")
        for email in recent_emails:
            meeting_info = extract_meeting_info(email)
            if meeting_info:
                meetings.append({
                    'id': f"email_{email.get('id')}",
                    'title': meeting_info.get('title', email.get('subject', 'No Title')),
                    'description': email.get('body', ''),
                    'start': None,  # Would need better parsing
                    'start_str': meeting_info.get('datetime', ''),
                    'end': None,
                    'location': '',
                    'source': 'email',
                    'email_id': email.get('id'),
                    'email_subject': email.get('subject', ''),
                    'email_from': email.get('from', '')
                })
    
    # Sort by start time
    meetings.sort(key=lambda x: x.get('start') or datetime.max)
    
    return meetings

def get_meetings_needing_reminders(reminder_times: List[timedelta]) -> List[Dict]:
    """Get meetings that need reminders based on reminder times."""
    now = datetime.now()
    # Check next 14 days (2 weeks) to catch all upcoming meetings
    meetings = get_all_meetings(days_ahead=14)
    
    reminders_needed = []
    
    for meeting in meetings:
        start = meeting.get('start')
        if not start:
            continue
        
        # Calculate time until meeting
        time_until = start - now
        
        # Check if any reminder time matches
        for reminder_time in reminder_times:
            # Check if we're within 1 minute of the reminder time
            time_diff = abs((time_until - reminder_time).total_seconds())
            if time_diff <= 60:  # Within 1 minute
                reminders_needed.append({
                    **meeting,
                    'reminder_time': reminder_time,
                    'time_until': time_until
                })
                break
    
    return reminders_needed

def format_reminder_message(meeting: Dict, reminder_time: timedelta) -> str:
    """Format a friendly, human reminder message for a meeting."""
    import random
    
    title = meeting.get('title', 'Meeting')
    start = meeting.get('start')
    location = meeting.get('location', '')
    description = meeting.get('description', '')
    
    # Format meeting time
    if start:
        time_formatted = start.strftime('%I:%M %p')
        date_formatted = start.strftime('%B %d')
        if start.date() == datetime.now().date():
            time_display = f"{time_formatted} today"
        else:
            time_display = f"{time_formatted} on {date_formatted}"
    else:
        time_display = "soon"
    
    # Format time until (for context)
    if reminder_time == timedelta(days=1):
        time_until = "tomorrow"
    elif reminder_time == timedelta(hours=1):
        time_until = "in 1 hour"
    elif reminder_time == timedelta(minutes=30):
        time_until = "in 30 minutes"
    elif reminder_time == timedelta(minutes=5):
        time_until = "in 5 minutes"
    else:
        time_until = f"in {reminder_time}"
    
    # Select a friendly, human message template
    templates = [
        # Soft & Friendly
        f"Just a quick reminder — you've got your {title} coming up at {time_display}. 😊",
        f"Hey! Don't forget about your {title} meeting at {time_display}. {time_until}!",
        f"Gently reminding you… your {title} meeting starts at {time_display}.",
        
        # Warm & Polite
        f"Hi there! This is a reminder that your {title} meeting is scheduled for {time_display}.",
        f"Hope you're having a good day! Your {title} meeting is at {time_display} — just a heads-up. {time_until}!",
        f"A little nudge — your {title} meeting begins at {time_display}.",
        
        # Casual & Human
        f"Hey, just wanted to remind you — your {title} is at {time_display}. Don't miss it! {time_until}.",
        f"Quick ping! You've got {title} at {time_display}. {time_until}!",
        f"FYI, your meeting ({title}) is happening at {time_display}. Thought you'd want a reminder 😊",
        
        # Supportive Tone
        f"You're doing great! Just a small reminder — {title} starts at {time_display}. {time_until}!",
        f"I'm here to keep you on track — your {title} meeting is at {time_display}. {time_until}!",
        f"Sending you a friendly reminder: {title} is happening at {time_display}. {time_until}!",
        
        # Human + Slightly Professional
        f"Friendly reminder: your {title} meeting is scheduled for {time_display}. {time_until}!",
        f"Reminder for you — {title} begins at {time_display}. {time_until}!",
        f"Your {title} meeting is coming up at {time_display} — just keeping you in the loop! {time_until}!",
        
        # Super Conversational
        f"Just popping in — your {title} meeting starts at {time_display}! {time_until}!",
        f"Hey! Your {title} at {time_display} is coming up soon. You got this! {time_until}.",
        f"Heads up! Your meeting ({title}) is almost here — {time_display}. {time_until}!",
        
        # Gentle & Humanitarian
        f"I hope you're doing well. Just reminding you that your {title} meeting begins at {time_display}. {time_until}!",
        f"A calm little reminder… your {title} starts at {time_display}. Take it easy. {time_until}!",
    ]
    
    # Randomly select a template for variety
    message = random.choice(templates)
    
    # Add location if available
    if location:
        message += f"\n📍 Location: {location}"
    
    # Add description if available (shortened)
    if description:
        desc_short = description[:150] + "..." if len(description) > 150 else description
        message += f"\n\n📝 {desc_short}"
    
    return message

