"""On-demand meeting and urgent email checker."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from gmail_client import get_gmail_service, get_calendar_service, get_recent_emails, detect_urgent_emails, get_upcoming_meetings
from meeting_detector import get_all_meetings, format_reminder_message

def check_meetings_and_emails() -> Dict:
    """Check for upcoming meetings and urgent emails."""
    result = {
        "meetings": [],
        "urgent_emails": [],
        "success": False,
        "error": None
    }
    
    try:
        # Get upcoming meetings from all sources (Google Calendar + iCalendar)
        from meeting_detector import get_all_meetings
        try:
            all_meetings = get_all_meetings(days_ahead=14)
            result["meetings"] = all_meetings[:10]  # Limit to 10 most recent
        except Exception as e:
            print(f"[MeetingChecker] Error getting meetings: {e}")
            # Fallback to Google Calendar only
            calendar_service = get_calendar_service()
            if calendar_service:
                meetings = get_upcoming_meetings(calendar_service, days_ahead=7)
                result["meetings"] = meetings[:10]
            else:
                result["error"] = "No calendar services available"
        
        # Get urgent emails
        gmail_service = get_gmail_service()
        if gmail_service:
            recent_emails = get_recent_emails(gmail_service, max_results=20, query="newer_than:7d")
            urgent_emails = detect_urgent_emails(recent_emails)
            result["urgent_emails"] = urgent_emails[:5]  # Limit to 5 most urgent
        else:
            if not result.get("error"):
                result["error"] = "Gmail API not available"
        
        result["success"] = True
        return result
    
    except Exception as e:
        result["error"] = str(e)
        return result

def _is_real_meeting(meeting: Dict) -> bool:
    """Check if this is a real meeting (not an email notification, etc.)."""
    title = meeting.get('title', '').lower()
    
    # Filter out non-meeting events
    non_meeting_keywords = [
        'confirm your application', 'application for', 'ticket is here',
        'member benefits', 'bulletin', 'newsletter', 'update:',
        'survivor series', 'netflix', 'streaming', 'watch now',
        'unsubscribe', 'email', 'notification', 'alert',
        'promotion', 'sale', 'discount', 'offer'
    ]
    
    # Skip if title contains non-meeting keywords
    if any(keyword in title for keyword in non_meeting_keywords):
        return False
    
    # Check if it has attendees or location (more likely to be a real meeting)
    has_attendees = len(meeting.get('attendees', [])) > 0
    has_location = bool(meeting.get('location', ''))
    has_start_time = bool(meeting.get('start'))
    
    # More likely to be a real meeting if it has attendees, location, or proper start time
    if has_attendees or has_location or has_start_time:
        return True
    
    # If title is very short or looks like an email subject, skip
    if len(title) < 5 or ':' in title[:20]:
        return False
    
    return True

def format_meetings_response(meetings: List[Dict]) -> str:
    """Format meetings list for user response in a natural, conversational way."""
    # Filter out non-meetings
    real_meetings = [m for m in meetings if _is_real_meeting(m)]
    
    if not real_meetings:
        return "You don't have any upcoming meetings in the next week. You're all clear! 😊"
    
    # Limit to 5 most relevant
    real_meetings = real_meetings[:5]
    
    meeting_count = len(real_meetings)
    response = f"You have {meeting_count} upcoming meeting"
    if meeting_count > 1:
        response += "s"
    response += ":\n\n"
    
    for i, meeting in enumerate(real_meetings, 1):
        title = meeting.get('title', 'Meeting')
        start = meeting.get('start')
        location = meeting.get('location', '')
        
        # Format time naturally
        if start:
            try:
                if isinstance(start, datetime):
                    dt = start
                else:
                    dt = datetime.fromisoformat(str(start).replace('Z', '+00:00'))
                
                # Natural time formatting
                if dt.date() == datetime.now().date():
                    time_str = f"today at {dt.strftime('%I:%M %p')}"
                elif dt.date() == (datetime.now() + timedelta(days=1)).date():
                    time_str = f"tomorrow at {dt.strftime('%I:%M %p')}"
                else:
                    time_str = f"{dt.strftime('%A, %B %d')} at {dt.strftime('%I:%M %p')}"
            except:
                time_str = meeting.get('start_str', 'soon')
        else:
            time_str = "soon"
        
        response += f"{i}. {title}\n"
        response += f"   {time_str}"
        if location:
            response += f" • {location}"
        response += "\n\n"
    
    if len(meetings) > len(real_meetings):
        filtered_count = len(meetings) - len(real_meetings)
        response += f"(Filtered out {filtered_count} non-meeting event{'s' if filtered_count > 1 else ''})\n"
    
    return response

def format_urgent_emails_response(emails: List[Dict]) -> str:
    """Format urgent emails list for user response in a natural way."""
    if not emails:
        return "No urgent emails in the last week. Your inbox looks good! 👍"
    
    response = f"You have {len(emails)} urgent email"
    if len(emails) > 1:
        response += "s"
    response += ":\n\n"
    
    for i, email in enumerate(emails[:3], 1):  # Show top 3
        subject = email.get('subject', 'No Subject')
        sender = email.get('from', 'Unknown')
        # Extract just the email or name from sender
        sender_clean = sender.split('<')[0].strip() or sender.split('<')[-1].replace('>', '').strip()
        snippet = email.get('snippet', '')[:80]
        
        response += f"{i}. {subject}\n"
        response += f"   From: {sender_clean}"
        if snippet:
            response += f"\n   \"{snippet}...\""
        response += "\n\n"
    
    return response

def get_meetings_and_emails_summary() -> str:
    """Get a summary of meetings and urgent emails."""
    check_result = check_meetings_and_emails()
    
    if not check_result.get("success"):
        return f"❌ Unable to check meetings/emails: {check_result.get('error', 'Unknown error')}"
    
    meetings = check_result.get("meetings", [])
    urgent_emails = check_result.get("urgent_emails", [])
    
    response = ""
    
    # Meetings section
    response += format_meetings_response(meetings)
    response += "\n"
    
    # Urgent emails section
    response += format_urgent_emails_response(urgent_emails)
    
    return response

