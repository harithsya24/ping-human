"""Scheduler for meeting reminders and urgent email notifications."""
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from meeting_detector import get_meetings_needing_reminders, format_reminder_message
from gmail_client import get_gmail_service, get_recent_emails, detect_urgent_emails
from series_api import send_message, create_chat
import os

# Reminder times: 1 day, 1 hour, 30 minutes, 5 minutes before meeting
REMINDER_TIMES = [
    timedelta(days=1),
    timedelta(hours=1),
    timedelta(minutes=30),
    timedelta(minutes=5)
]

# User's phone number for sending reminders
USER_PHONE = os.getenv("SENDER_NUMBER", "+16463769330")
RECIPIENT_NUMBER = os.getenv("RECIPIENT_NUMBER", "+12017056654")  # Number to send reminders to
REMINDER_CHAT_ID = os.getenv("REMINDER_CHAT_ID")  # Optional: specific chat ID for reminders

class ReminderScheduler:
    """Manages meeting reminders and urgent email notifications."""
    
    def __init__(self, send_reminder_callback: Optional[Callable] = None, ai_client=None):
        """
        Initialize the reminder scheduler.
        
        Args:
            send_reminder_callback: Optional callback function to send reminders.
                                   If None, uses Series API directly.
            ai_client: Optional OpenAI client for intelligent email classification.
        """
        self.send_reminder_callback = send_reminder_callback
        self.ai_client = ai_client
        self.running = False
        self.thread = None
        self.sent_reminders = set()  # Track sent reminders to avoid duplicates
        self.last_urgent_check = None
    
    def send_reminder(self, message: str, meeting_id: str = None):
        """Send a reminder message to the user."""
        if self.send_reminder_callback:
            # Use callback (e.g., from bot_service)
            self.send_reminder_callback(message)
        else:
            # Use Series API directly - send to recipient number
            try:
                if REMINDER_CHAT_ID:
                    send_message(int(REMINDER_CHAT_ID), message)
                    print(f"[ReminderScheduler] ✅ Reminder sent to chat {REMINDER_CHAT_ID}")
                else:
                    # Format recipient number (ensure +1 prefix)
                    recipient = RECIPIENT_NUMBER
                    if not recipient.startswith("+"):
                        if recipient.startswith("1") and len(recipient) == 11:
                            recipient = f"+{recipient}"
                        elif len(recipient) == 10:
                            recipient = f"+1{recipient}"
                    
                    # Create chat with recipient number and send reminder
                    create_chat(
                        phone_numbers=[recipient],
                        message_text=message,
                        display_name="Meeting Reminder"
                    )
                    print(f"[ReminderScheduler] ✅ Reminder sent to {recipient}")
            except Exception as e:
                print(f"[ReminderScheduler] ❌ Error sending reminder: {e}")
                import traceback
                traceback.print_exc()
    
    def check_meeting_reminders(self):
        """Check for meetings that need reminders."""
        try:
            reminders = get_meetings_needing_reminders(REMINDER_TIMES)
            
            for reminder in reminders:
                meeting_id = reminder.get('id')
                reminder_time = reminder.get('reminder_time')
                
                # Create unique key for this reminder
                reminder_key = f"{meeting_id}_{reminder_time}"
                
                # Skip if already sent
                if reminder_key in self.sent_reminders:
                    continue
                
                # Format and send reminder
                message = format_reminder_message(reminder, reminder_time)
                self.send_reminder(message, meeting_id)
                
                # Mark as sent
                self.sent_reminders.add(reminder_key)
                print(f"[ReminderScheduler] 📅 Reminder sent for meeting: {reminder.get('title')}")
        
        except Exception as e:
            print(f"[ReminderScheduler] ❌ Error checking meeting reminders: {e}")
            import traceback
            traceback.print_exc()
    
    def check_urgent_emails(self, ai_client=None):
        """Check for urgent emails and send notifications (limited to avoid spam)."""
        try:
            gmail_service = get_gmail_service()
            if not gmail_service:
                return
            
            # Get recent emails (last 24 hours)
            recent_emails = get_recent_emails(gmail_service, max_results=30, query="newer_than:1d")
            
            if not recent_emails:
                return
            
            # Detect urgent emails using AI classification (max 3 per check)
            from gmail_client import detect_urgent_emails
            urgent_emails = detect_urgent_emails(recent_emails, ai_client=ai_client, max_urgent=3)
            
            if not urgent_emails:
                return
            
            # Send notifications for truly urgent emails only
            sent_count = 0
            for email in urgent_emails:
                email_id = email.get('id')
                
                # Skip if already notified
                if email_id in self.sent_reminders:
                    continue
                
                # Format urgent email notification
                subject = email.get('subject', 'No Subject')
                sender = email.get('from', 'Unknown')
                snippet = email.get('snippet', '')[:200]
                urgency_reason = email.get('urgency_reason', 'Classified as urgent')
                
                message = f"🚨 Urgent Email Alert\n\n"
                message += f"📧 From: {sender}\n"
                message += f"📌 Subject: {subject}\n"
                message += f"💬 Preview: {snippet}...\n\n"
                message += f"⚠️ {urgency_reason}"
                
                self.send_reminder(message, email_id)
                
                # Mark as notified
                self.sent_reminders.add(email_id)
                sent_count += 1
                print(f"[ReminderScheduler] 🚨 Urgent email notification sent: {subject[:50]}")
                
                # Limit to max 3 urgent emails per check
                if sent_count >= 3:
                    break
        
        except Exception as e:
            print(f"[ReminderScheduler] ❌ Error checking urgent emails: {e}")
            import traceback
            traceback.print_exc()
    
    def run_loop(self):
        """Main loop for checking reminders."""
        print("[ReminderScheduler] 🚀 Starting reminder scheduler...")
        self.running = True
        
        while self.running:
            try:
                # Check meeting reminders every minute
                self.check_meeting_reminders()
                
                # Check urgent emails every 5 minutes
                now = datetime.now()
                if not self.last_urgent_check or (now - self.last_urgent_check).total_seconds() >= 300:
                    self.check_urgent_emails(self.ai_client)
                    self.last_urgent_check = now
                
                # Sleep for 1 minute
                time.sleep(60)
            
            except Exception as e:
                print(f"[ReminderScheduler] ❌ Error in reminder loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)  # Continue after error
    
    def start(self):
        """Start the reminder scheduler in a background thread."""
        if self.running:
            print("[ReminderScheduler] Already running")
            return
        
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        print("[ReminderScheduler] ✅ Started in background thread")
    
    def stop(self):
        """Stop the reminder scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[ReminderScheduler] ⏹️ Stopped")

# Global scheduler instance
_scheduler: Optional[ReminderScheduler] = None

def get_scheduler(send_reminder_callback: Optional[Callable] = None, ai_client=None) -> ReminderScheduler:
    """Get or create the global reminder scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReminderScheduler(send_reminder_callback, ai_client)
    return _scheduler

def start_reminder_scheduler(send_reminder_callback: Optional[Callable] = None, ai_client=None):
    """Start the reminder scheduler."""
    scheduler = get_scheduler(send_reminder_callback, ai_client)
    scheduler.start()

def stop_reminder_scheduler():
    """Stop the reminder scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()

