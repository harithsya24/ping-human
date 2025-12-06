"""iCalendar integration for reading macOS Calendar events."""
import os
import subprocess
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import re

def get_icalendar_events(days_ahead: int = 14) -> List[Dict]:
    """
    Get calendar events from macOS Calendar app using AppleScript.
    Returns events for the next N days.
    """
    applescript = f'''
    tell application "Calendar"
        set output to ""
        set today to current date
        set futureDate to today + ({days_ahead} * days)
        
        repeat with aCal in calendars
            repeat with anEvent in (every event of aCal whose start date is greater than or equal to today and start date is less than or equal to futureDate)
                set eventInfo to ""
                
                -- Event title
                set eventInfo to eventInfo & "TITLE:" & summary of anEvent & "|"
                
                -- Start date/time
                set startDate to start date of anEvent
                set eventInfo to eventInfo & "START:" & (startDate as string) & "|"
                
                -- End date/time
                set endDate to end date of anEvent
                set eventInfo to eventInfo & "END:" & (endDate as string) & "|"
                
                -- Location
                try
                    set eventInfo to eventInfo & "LOCATION:" & location of anEvent & "|"
                on error
                    set eventInfo to eventInfo & "LOCATION:|"
                end try
                
                -- Description/Notes
                try
                    set eventInfo to eventInfo & "DESCRIPTION:" & description of anEvent & "|"
                on error
                    set eventInfo to eventInfo & "DESCRIPTION:|"
                end try
                
                -- Attendees
                try
                    set attendeesList to ""
                    repeat with anAttendee in attendees of anEvent
                        set attendeesList to attendeesList & (email of anAttendee) & ","
                    end repeat
                    set eventInfo to eventInfo & "ATTENDEES:" & attendeesList & "|"
                on error
                    set eventInfo to eventInfo & "ATTENDEES:|"
                end try
                
                -- Calendar name
                set eventInfo to eventInfo & "CALENDAR:" & name of aCal & "|"
                
                -- Recurrence
                try
                    set eventInfo to eventInfo & "RECURRENCE:" & recurrence of anEvent & "|"
                on error
                    set eventInfo to eventInfo & "RECURRENCE:|"
                end try
                
                set output to output & eventInfo & "\\n"
            end repeat
        end repeat
        
        return output
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout for large calendars
        )
        
        if result.returncode != 0:
            print(f"[iCalendar] AppleScript error: {result.stderr}")
            return []
        
        events = []
        for line in result.stdout.strip().split('\n'):
            if not line or 'TITLE:' not in line:
                continue
            
            try:
                event = _parse_icalendar_line(line)
                if event:
                    events.append(event)
            except Exception as e:
                print(f"[iCalendar] Error parsing event line: {e}")
                continue
        
        # Sort by start time
        events.sort(key=lambda x: x.get('start', ''))
        
        print(f"[iCalendar] ✅ Found {len(events)} events from macOS Calendar")
        return events
    
    except subprocess.TimeoutExpired:
        print("[iCalendar] Timeout accessing Calendar app")
        return []
    except Exception as e:
        print(f"[iCalendar] Error: {e}")
        return []

def _parse_icalendar_line(line: str) -> Optional[Dict]:
    """Parse a line of calendar event data from AppleScript."""
    event = {}
    
    # Extract fields
    title_match = re.search(r'TITLE:(.*?)\|', line)
    start_match = re.search(r'START:(.*?)\|', line)
    end_match = re.search(r'END:(.*?)\|', line)
    location_match = re.search(r'LOCATION:(.*?)\|', line)
    description_match = re.search(r'DESCRIPTION:(.*?)\|', line)
    attendees_match = re.search(r'ATTENDEES:(.*?)\|', line)
    calendar_match = re.search(r'CALENDAR:(.*?)\|', line)
    recurrence_match = re.search(r'RECURRENCE:(.*?)\|', line)
    
    if not title_match:
        return None
    
    event['title'] = title_match.group(1).strip()
    
    if start_match:
        start_str = start_match.group(1).strip()
        event['start'] = _parse_apple_date(start_str)
        event['start_str'] = start_str
    else:
        event['start'] = None
        event['start_str'] = ''
    
    if end_match:
        end_str = end_match.group(1).strip()
        event['end'] = _parse_apple_date(end_str)
        event['end_str'] = end_str
    else:
        event['end'] = None
        event['end_str'] = ''
    
    event['location'] = location_match.group(1).strip() if location_match else ''
    event['description'] = description_match.group(1).strip() if description_match else ''
    
    if attendees_match:
        attendees_str = attendees_match.group(1).strip()
        event['attendees'] = [a.strip() for a in attendees_str.split(',') if a.strip()]
    else:
        event['attendees'] = []
    
    event['calendar'] = calendar_match.group(1).strip() if calendar_match else 'Default'
    event['recurrence'] = recurrence_match.group(1).strip() if recurrence_match else ''
    event['source'] = 'icalendar'
    
    return event

def _parse_apple_date(date_str: str) -> Optional[datetime]:
    """Parse AppleScript date string to datetime."""
    if not date_str or date_str == 'missing value':
        return None
    
    # AppleScript dates are in format: "Monday, January 15, 2024 at 2:00:00 PM"
    # Or: "2024-01-15 14:00:00"
    
    # Try ISO format first
    try:
        if 'T' in date_str or '-' in date_str:
            # ISO format or similar
            date_str_clean = date_str.replace(' at ', 'T').replace(' ', 'T', 1)
            if 'T' in date_str_clean:
                dt_str, time_str = date_str_clean.split('T', 1)
                # Parse date part
                year, month, day = dt_str.split('-')
                # Parse time part
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                second = int(time_parts[2].split()[0]) if len(time_parts) > 2 else 0
                
                # Check for AM/PM
                if 'PM' in time_str and hour < 12:
                    hour += 12
                elif 'AM' in time_str and hour == 12:
                    hour = 0
                
                return datetime(int(year), int(month), int(day), hour, minute, second)
    except:
        pass
    
    # Try common date formats
    formats = [
        '%A, %B %d, %Y at %I:%M:%S %p',
        '%B %d, %Y at %I:%M:%S %p',
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y %I:%M %p',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    
    return None

def get_upcoming_icalendar_meetings(days_ahead: int = 14) -> List[Dict]:
    """Get upcoming meetings from macOS Calendar."""
    events = get_icalendar_events(days_ahead)
    
    # Filter for meetings (events with attendees or specific keywords)
    meetings = []
    for event in events:
        title = event.get('title', '').lower()
        has_attendees = len(event.get('attendees', [])) > 0
        
        # Consider it a meeting if it has attendees or contains meeting keywords
        is_meeting = (
            has_attendees or
            any(keyword in title for keyword in ['meeting', 'call', 'conference', 'standup', 'sync', 'appointment'])
        )
        
        if is_meeting:
            meetings.append({
                'id': f"ical_{event.get('title', '')}_{event.get('start_str', '')}",
                'title': event.get('title', 'No Title'),
                'description': event.get('description', ''),
                'start': event.get('start'),
                'start_str': event.get('start_str', ''),
                'end': event.get('end'),
                'end_str': event.get('end_str', ''),
                'location': event.get('location', ''),
                'attendees': event.get('attendees', []),
                'calendar': event.get('calendar', ''),
                'source': 'icalendar'
            })
    
    return meetings

def check_icalendar_setup() -> Dict:
    """Check if macOS Calendar is accessible."""
    try:
        # Quick check - just try to access Calendar app
        result = subprocess.run(
            ['osascript', '-e', 'tell application "Calendar" to get name'],
            capture_output=True,
            text=True,
            timeout=60  # 1 minute for setup check
        )
        
        if result.returncode == 0:
            return {
                "configured": True,
                "message": "macOS Calendar is accessible. iCalendar integration ready.",
                "calendars": []
            }
        else:
            return {
                "configured": False,
                "message": "macOS Calendar not accessible. Please grant Calendar app permission in System Settings > Privacy & Security > Automation."
            }
    except subprocess.TimeoutExpired:
        return {
            "configured": False,
            "message": "Calendar app access timed out. Make sure Calendar app is running and has automation permissions."
        }
    except Exception as e:
        return {
            "configured": False,
            "message": f"Error accessing Calendar: {str(e)}. Please grant Calendar app permission in System Settings."
        }

