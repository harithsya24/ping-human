"""On-demand meeting and urgent email checker."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from gmail_client import get_gmail_service, get_calendar_service, get_recent_emails, detect_urgent_emails, get_upcoming_meetings
from meeting_detector import get_all_meetings, format_reminder_message

def check_meetings_and_emails() -> Dict:
    """Check for upcoming meetings and urgent emails - fast and simple, just output what we see."""
    result = {
        "meetings": [],
        "urgent_emails": [],
        "success": False,
        "error": None
    }
    
    try:
        # Fast check with shorter timeout - just get what we can quickly
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
        
        def check_all():
            local_result = {
                "meetings": [],
                "urgent_emails": [],
                "success": False,
                "error": None
            }
            
            # Try to get meetings quickly - use shorter time range
            try:
                calendar_service = get_calendar_service()
                if calendar_service:
                    # Just get next 7 days, limit to 5 meetings
                    meetings = get_upcoming_meetings(calendar_service, days_ahead=7)
                    # Just take what we see, minimal processing
                    local_result["meetings"] = meetings[:5]
                else:
                    # Fallback to meeting_detector but with shorter range
                    from meeting_detector import get_all_meetings
                    all_meetings = get_all_meetings(days_ahead=7)  # Reduced from 14
                    local_result["meetings"] = all_meetings[:5]  # Reduced from 10
            except Exception as e:
                print(f"[MeetingChecker] Error getting meetings: {e}")
                local_result["error"] = f"Calendar error: {str(e)}"
            
            # Try to get emails quickly - limit results
            try:
                gmail_service = get_gmail_service()
                if gmail_service:
                    # Just get recent emails, minimal processing
                    recent_emails = get_recent_emails(gmail_service, max_results=10, query="newer_than:3d")  # Reduced from 20 and 7d
                    # Simple urgent detection - just check subject/sender, no complex AI
                    urgent_emails = [e for e in recent_emails if any(word in e.get('subject', '').lower() for word in ['urgent', 'asap', 'important', 'action required'])]
                    local_result["urgent_emails"] = urgent_emails[:3]  # Reduced from 5
            except Exception as e:
                print(f"[MeetingChecker] Error getting emails: {e}")
                if not local_result.get("error"):
                    local_result["error"] = f"Email error: {str(e)}"
            
            local_result["success"] = True
            return local_result
        
        # Reduced timeout to 10 seconds for faster response
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(check_all)
            result = future.result(timeout=10)  # Reduced from 40s
        
        return result
    
    except FutureTimeoutError:
        result["error"] = "Request timed out (10s limit)"
        result["success"] = False
        return result
    except Exception as e:
        result["error"] = str(e)
        return result

# Removed _is_real_meeting - we just show what we see, no filtering

def format_meetings_response(meetings: List[Dict]) -> str:
    """Format meetings list - simple output, just show what we see."""
    if not meetings:
        return "No upcoming meetings found."
    
    response = f"Upcoming meetings ({len(meetings)}):\n\n"
    
    for i, meeting in enumerate(meetings, 1):
        title = meeting.get('title', 'Meeting')
        start = meeting.get('start')
        location = meeting.get('location', '')
        
        # Simple time formatting - just show what we have
        if start:
            try:
                if isinstance(start, datetime):
                    dt = start
                elif isinstance(start, str):
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                else:
                    dt = start
                
                time_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                time_str = str(start) if start else "TBD"
        else:
            time_str = "TBD"
        
        response += f"{i}. {title}\n"
        response += f"   Time: {time_str}"
        if location:
            response += f"\n   Location: {location}"
        response += "\n\n"
    
    return response

def format_urgent_emails_response(emails: List[Dict]) -> str:
    """Format urgent emails - simple output, just show what we see."""
    if not emails:
        return "No urgent emails found."
    
    response = f"Urgent emails ({len(emails)}):\n\n"
    
    for i, email in enumerate(emails, 1):
        subject = email.get('subject', 'No Subject')
        sender = email.get('from', 'Unknown')
        
        response += f"{i}. {subject}\n"
        response += f"   From: {sender}\n\n"
    
    return response

def get_meetings_and_emails_summary() -> str:
    """Get a summary of meetings and urgent emails."""
    check_result = check_meetings_and_emails()
    
    if not check_result.get("success"):
        return f"[ERROR] Unable to check meetings/emails: {check_result.get('error', 'Unknown error')}"
    
    meetings = check_result.get("meetings", [])
    urgent_emails = check_result.get("urgent_emails", [])
    
    response = ""
    
    # Meetings section
    response += format_meetings_response(meetings)
    response += "\n"
    
    # Urgent emails section
    response += format_urgent_emails_response(urgent_emails)
    
    return response

