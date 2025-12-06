"""Scheduler for meeting reminders and urgent email notifications."""
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from meeting_detector import get_meetings_needing_reminders, format_reminder_message
from gmail_client import get_gmail_service, get_recent_emails, detect_urgent_emails
from series_api import send_message, create_chat
from action_history import log_action
from notification_preferences import should_send_proactive_reminder, get_urgent_email_limit
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
    
    def send_reminder(self, message: str, meeting_id: str = None, reminder_type: str = "meeting"):
        """Send a reminder message to the user."""
        if not should_send_proactive_reminder(reminder_type):
            print(f"[ReminderScheduler] ⏸️  Proactive {reminder_type} reminders disabled by user preference")
            return
        
        if self.send_reminder_callback:
            self.send_reminder_callback(message)
            log_action("reminder_sent", {
                "type": reminder_type,
                "meeting_id": meeting_id,
                "message": message,
                "success": True,
                "proactive": True
            })
        else:
            try:
                if REMINDER_CHAT_ID:
                    send_message(int(REMINDER_CHAT_ID), message)
                    log_action("reminder_sent", {
                        "type": "meeting",
                        "meeting_id": meeting_id,
                        "chat_id": REMINDER_CHAT_ID,
                        "message": message,
                        "success": True
                    })
                    print(f"[ReminderScheduler] ✅ Reminder sent to chat {REMINDER_CHAT_ID}")
                else:
                    recipient = RECIPIENT_NUMBER
                    if not recipient.startswith("+"):
                        if recipient.startswith("1") and len(recipient) == 11:
                            recipient = f"+{recipient}"
                        elif len(recipient) == 10:
                            recipient = f"+1{recipient}"
                    
                    create_chat(
                        phone_numbers=[recipient],
                        message_text=message,
                        display_name="Meeting Reminder"
                    )
                    log_action("reminder_sent", {
                        "type": "meeting",
                        "meeting_id": meeting_id,
                        "recipient": recipient,
                        "message": message,
                        "success": True,
                        "proactive": True
                    })
                    print(f"[ReminderScheduler] ✅ Reminder sent to {recipient}")
            except Exception as e:
                log_action("reminder_sent", {
                    "type": "meeting",
                    "meeting_id": meeting_id,
                    "message": message,
                    "success": False,
                    "error": str(e)
                })
                print(f"[ReminderScheduler] ❌ Error sending reminder: {e}")
                import traceback
                traceback.print_exc()
    
    def check_meeting_reminders(self):
        """Check for meetings that need reminders (non-blocking, with timeout). STRICT: Reminders are separate from conversation logs."""
        try:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
            
            def check_reminders():
                reminders = get_meetings_needing_reminders(REMINDER_TIMES)
                
                for reminder in reminders:
                    meeting_id = reminder.get('id')
                    reminder_time = reminder.get('reminder_time')
                    
                    reminder_key = f"{meeting_id}_{reminder_time}"
                    
                    if reminder_key in self.sent_reminders:
                        continue
                    
                    message = format_reminder_message(reminder, reminder_time)
                    self.send_reminder(message, meeting_id, reminder_type="meeting")
                    
                    self.sent_reminders.add(reminder_key)
                    print(f"[ReminderScheduler] 📅 Reminder sent for meeting: {reminder.get('title')}")
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(check_reminders)
                future.result(timeout=90)
        
        except FutureTimeoutError:
            print(f"[ReminderScheduler] ⚠️  Meeting reminder check timed out (90s), skipping this cycle")
        except Exception as e:
            print(f"[ReminderScheduler] ❌ Error checking meeting reminders: {e}")
            import traceback
            traceback.print_exc()
    
    def check_urgent_emails(self, ai_client=None):
        """Check for urgent emails and send notifications (non-blocking, with timeout). STRICT: Email alerts are separate from conversation logs."""
        try:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
            
            def check_emails():
                gmail_service = get_gmail_service()
                if not gmail_service:
                    return
                
                recent_emails = get_recent_emails(gmail_service, max_results=30, query="newer_than:1d")
                
                if not recent_emails:
                    return
                
                from gmail_client import detect_urgent_emails
                max_urgent = get_urgent_email_limit()
                urgent_emails = detect_urgent_emails(recent_emails, ai_client=ai_client, max_urgent=max_urgent)
                
                if not urgent_emails:
                    return
                
                sent_count = 0
                for email in urgent_emails:
                    email_id = email.get('id')
                    
                    if email_id in self.sent_reminders:
                        continue
                    
                    subject = email.get('subject', 'No Subject')
                    sender = email.get('from', 'Unknown')
                    snippet = email.get('snippet', '')[:200]
                    urgency_reason = email.get('urgency_reason', 'Classified as urgent')
                    
                    message = f"🚨 Urgent Email Alert\n\n"
                    message += f"📧 From: {sender}\n"
                    message += f"📌 Subject: {subject}\n"
                    message += f"💬 Preview: {snippet}...\n\n"
                    message += f"⚠️ {urgency_reason}"
                    
                    self.send_reminder(message, email_id, reminder_type="urgent_email")
                    
                    log_action("reminder_sent", {
                        "type": "urgent_email",
                        "email_id": email_id,
                        "subject": subject,
                        "from": sender,
                        "message": message,
                        "success": True,
                        "proactive": True
                    })
                    
                    self.sent_reminders.add(email_id)
                    sent_count += 1
                    print(f"[ReminderScheduler] 🚨 Urgent email notification sent: {subject[:50]}")
                    
                    max_urgent = get_urgent_email_limit()
                    if sent_count >= max_urgent:
                        break
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(check_emails)
                future.result(timeout=20)
        
        except FutureTimeoutError:
            print(f"[ReminderScheduler] ⚠️  Urgent email check timed out (20s), skipping this cycle")
        except Exception as e:
            print(f"[ReminderScheduler] ❌ Error checking urgent emails: {e}")
            import traceback
            traceback.print_exc()
    
    def run_loop(self):
        """Main loop for checking reminders (non-blocking, error-resilient)."""
        print("[ReminderScheduler] 🚀 Starting reminder scheduler...")
        self.running = True
        
        while self.running:
            try:
                try:
                    self.check_meeting_reminders()
                except Exception as e:
                    print(f"[ReminderScheduler] ⚠️  Meeting reminder check failed (non-blocking): {e}")
                
                now = datetime.now()
                if not self.last_urgent_check or (now - self.last_urgent_check).total_seconds() >= 300:
                    try:
                        self.check_urgent_emails(self.ai_client)
                        self.last_urgent_check = now
                    except Exception as e:
                        print(f"[ReminderScheduler] ⚠️  Urgent email check failed (non-blocking): {e}")
                        self.last_urgent_check = now
                
                time.sleep(60)
            
            except KeyboardInterrupt:
                print("[ReminderScheduler] Stopping reminder scheduler...")
                break
            except Exception as e:
                print(f"[ReminderScheduler] ❌ Error in reminder loop (will retry): {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)
    
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

