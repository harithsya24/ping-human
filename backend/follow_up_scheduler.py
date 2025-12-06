"""Follow-up message scheduler - tracks sent messages and schedules follow-ups if no reply."""
import threading
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from series_api import create_chat
from messaging_rules import get_allowed_recipient
from action_history import log_action

# File to persist follow-up data
FOLLOW_UP_DATA_FILE = "follow_up_data.json"

# Configuration (Fast testing mode)
REPLY_WAIT_MINUTES = 1  # Wait 1 minute for a reply (fast testing)
FOLLOW_UP_DELAY_HOURS = 2 / 60  # Schedule follow-up 2 minutes later if no reply (2/60 hours = 2 minutes)
MAX_FOLLOW_UPS = 2  # Maximum number of follow-ups to send (2 times max)

class FollowUpScheduler:
    """Manages follow-up messages for sent messages."""
    
    def __init__(self, send_message_callback: Optional[Callable] = None):
        """
        Initialize the follow-up scheduler.
        
        Args:
            send_message_callback: Optional callback function to send follow-up messages.
                                 If None, uses Series API directly.
        """
        self.send_message_callback = send_message_callback
        self.running = False
        self.thread = None
        self.pending_follow_ups: Dict[str, dict] = {}  # chat_id -> follow_up_info
        self.sent_messages: Dict[str, dict] = {}  # chat_id -> sent_message_info
        self._load_data()
    
    def _load_data(self):
        """Load follow-up data from file."""
        if os.path.exists(FOLLOW_UP_DATA_FILE):
            try:
                with open(FOLLOW_UP_DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.pending_follow_ups = data.get("pending_follow_ups", {})
                    self.sent_messages = data.get("sent_messages", {})
                    
                    # Convert timestamp strings back to datetime for comparison
                    for chat_id, info in self.pending_follow_ups.items():
                        if "sent_at" in info:
                            info["sent_at"] = datetime.fromisoformat(info["sent_at"])
                        if "follow_up_at" in info:
                            info["follow_up_at"] = datetime.fromisoformat(info["follow_up_at"])
                        # Ensure follow_up_count exists (for backward compatibility)
                        if "follow_up_count" not in info:
                            info["follow_up_count"] = 0
                    
                    for chat_id, info in self.sent_messages.items():
                        if "sent_at" in info:
                            info["sent_at"] = datetime.fromisoformat(info["sent_at"])
                    
                    print(f"[FollowUpScheduler] [OK] Loaded {len(self.pending_follow_ups)} pending follow-ups")
            except Exception as e:
                print(f"[FollowUpScheduler] [WARNING] Error loading follow-up data: {e}")
                self.pending_follow_ups = {}
                self.sent_messages = {}
    
    def _save_data(self):
        """Save follow-up data to file."""
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            data_to_save = {
                "pending_follow_ups": {},
                "sent_messages": {}
            }
            
            for chat_id, info in self.pending_follow_ups.items():
                info_copy = info.copy()
                if "sent_at" in info_copy and isinstance(info_copy["sent_at"], datetime):
                    info_copy["sent_at"] = info_copy["sent_at"].isoformat()
                if "follow_up_at" in info_copy and isinstance(info_copy["follow_up_at"], datetime):
                    info_copy["follow_up_at"] = info_copy["follow_up_at"].isoformat()
                data_to_save["pending_follow_ups"][chat_id] = info_copy
            
            for chat_id, info in self.sent_messages.items():
                info_copy = info.copy()
                if "sent_at" in info_copy and isinstance(info_copy["sent_at"], datetime):
                    info_copy["sent_at"] = info_copy["sent_at"].isoformat()
                data_to_save["sent_messages"][chat_id] = info_copy
            
            with open(FOLLOW_UP_DATA_FILE, 'w') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            print(f"[FollowUpScheduler] [WARNING] Error saving follow-up data: {e}")
    
    def track_sent_message(
        self,
        chat_id: str,
        recipient_phone: str,
        recipient_name: str,
        message_text: str,
        original_chat_id: Optional[str] = None
    ):
        """
        Track a message sent to a friend.
        
        Args:
            chat_id: The chat ID where message was sent
            recipient_phone: Phone number of the recipient
            recipient_name: Name of the recipient
            message_text: The message that was sent
            original_chat_id: Original chat ID (if message was sent from a different chat)
        """
        now = datetime.now()
        reply_deadline = now + timedelta(minutes=REPLY_WAIT_MINUTES)
        follow_up_time = now + timedelta(hours=FOLLOW_UP_DELAY_HOURS)
        
        follow_up_info = {
            "chat_id": chat_id,
            "recipient_phone": recipient_phone,
            "recipient_name": recipient_name,
            "message_text": message_text,
            "sent_at": now,
            "reply_deadline": reply_deadline,
            "follow_up_at": follow_up_time,
            "original_chat_id": original_chat_id,
            "reply_received": False,
            "follow_up_sent": False,
            "follow_up_count": 0  # Track how many follow-ups have been sent
        }
        
        self.pending_follow_ups[chat_id] = follow_up_info
        self.sent_messages[chat_id] = {
            "recipient_phone": recipient_phone,
            "recipient_name": recipient_name,
            "message_text": message_text,
            "sent_at": now
        }
        
        self._save_data()
        
        print(f"[FollowUpScheduler]  Tracking message to {recipient_name} ({recipient_phone})")
        print(f"[FollowUpScheduler]  Will check for reply at {reply_deadline.strftime('%H:%M:%S')}")
        print(f"[FollowUpScheduler]  Follow-up scheduled for {follow_up_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def check_for_reply(self, chat_id: str, sender_phone: str) -> bool:
        """
        Check if a reply was received for a tracked message.
        
        Args:
            chat_id: The chat ID where reply was received
            sender_phone: Phone number of the sender
            
        Returns:
            True if this was a reply to a tracked message, False otherwise
        """
        # Check if we're tracking this chat
        if chat_id not in self.pending_follow_ups:
            return False
        
        follow_up_info = self.pending_follow_ups[chat_id]
        
        # Check if the sender matches the recipient
        recipient_phone = follow_up_info.get("recipient_phone", "")
        
        # Normalize phone numbers for comparison
        def normalize_phone(phone: str) -> str:
            if not phone:
                return ""
            # Remove all non-digit characters except leading +
            cleaned = phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").strip()
            # If it starts with +, keep it; otherwise remove +
            if cleaned.startswith("+"):
                return cleaned
            # If it's 10 digits, add +1; if 11 digits starting with 1, add +
            digits = ''.join(filter(str.isdigit, cleaned))
            if len(digits) == 10:
                return f"+1{digits}"
            elif len(digits) == 11 and digits.startswith("1"):
                return f"+{digits}"
            return cleaned
        
        sender_normalized = normalize_phone(sender_phone)
        recipient_normalized = normalize_phone(recipient_phone)
        
        print(f"[FollowUpScheduler]  Checking reply: chat_id={chat_id}, "
              f"sender={sender_normalized}, recipient={recipient_normalized}")
        
        if sender_normalized == recipient_normalized and sender_normalized:
            # This is a reply! Cancel the follow-up
            print(f"[FollowUpScheduler] [OK] Reply received from {follow_up_info.get('recipient_name')}!")
            print(f"[FollowUpScheduler] [BLOCKED] Canceling follow-up for chat {chat_id}")
            
            follow_up_info["reply_received"] = True
            follow_up_info["reply_received_at"] = datetime.now()
            
            # Remove from pending follow-ups since reply was received
            del self.pending_follow_ups[chat_id]
            self._save_data()
            
            return True
        
        # Also check by phone number across all pending follow-ups (in case chat_id doesn't match)
        if not sender_normalized:
            return False
            
        for tracked_chat_id, tracked_info in list(self.pending_follow_ups.items()):
            if tracked_chat_id == chat_id:
                continue  # Already checked above
            
            tracked_recipient_phone = tracked_info.get("recipient_phone", "")
            tracked_recipient_normalized = normalize_phone(tracked_recipient_phone)
            
            if sender_normalized == tracked_recipient_normalized and sender_normalized:
                # Found a match by phone number!
                print(f"[FollowUpScheduler] [OK] Reply received from {tracked_info.get('recipient_name')} "
                      f"(matched by phone: {sender_normalized}, chat_id={tracked_chat_id})!")
                print(f"[FollowUpScheduler] [BLOCKED] Canceling follow-up for chat {tracked_chat_id}")
                
                tracked_info["reply_received"] = True
                tracked_info["reply_received_at"] = datetime.now()
                
                # Remove from pending follow-ups since reply was received
                del self.pending_follow_ups[tracked_chat_id]
                self._save_data()
                
                return True
        
        return False
    
    def send_follow_up(self, follow_up_info: dict):
        """Send a follow-up message from the user (not the bot)."""
        recipient_phone = follow_up_info.get("recipient_phone")
        recipient_name = follow_up_info.get("recipient_name", "Friend")
        original_message = follow_up_info.get("message_text", "")
        chat_id = follow_up_info.get("chat_id")
        follow_up_count = follow_up_info.get("follow_up_count", 0)
        
        # Check if we've reached the maximum follow-up limit
        if follow_up_count >= MAX_FOLLOW_UPS:
            print(f"[FollowUpScheduler] ⛔ Maximum follow-ups ({MAX_FOLLOW_UPS}) reached for {recipient_name}. No more follow-ups will be sent.")
            # Remove from pending follow-ups
            if chat_id in self.pending_follow_ups:
                del self.pending_follow_ups[chat_id]
            self._save_data()
            return
        
        # Generate follow-up message (as if from the user)
        follow_up_message = f"Hey {recipient_name}, just following up on my previous message. Let me know if you got a chance to see it!"
        
        try:
            if self.send_message_callback:
                # Use callback which should send from user's number
                self.send_message_callback(recipient_phone, follow_up_message, chat_id)
            else:
                # Use Series API directly - send from user's number
                import os
                from dotenv import load_dotenv
                load_dotenv()
                
                sender_number = os.getenv("SENDER_NUMBER")  # User's phone number
                if not sender_number:
                    print("[FollowUpScheduler] [WARNING] SENDER_NUMBER not set, cannot send from user")
                    raise ValueError("SENDER_NUMBER environment variable not set")
                
                recipient = recipient_phone
                if not recipient.startswith("+"):
                    if recipient.startswith("1") and len(recipient) == 11:
                        recipient = f"+{recipient}"
                    elif len(recipient) == 10:
                        recipient = f"+1{recipient}"
                
                # Send message using create_chat which uses send_from (user's number)
                # This makes it appear as if the message is from the user, not the bot
                create_chat(
                    phone_numbers=[recipient],
                    message_text=follow_up_message,
                    display_name=recipient_name,  # Use recipient name, not "Follow-up to..."
                    enforce_recipient=False
                )
                print(f"[FollowUpScheduler] 📤 Follow-up sent from user ({sender_number}) to {recipient_name} ({recipient})")
            
            # Increment follow-up count
            follow_up_info["follow_up_count"] = follow_up_count + 1
            follow_up_info["follow_up_sent"] = True
            follow_up_info["follow_up_sent_at"] = datetime.now()
            
            # Check if we should schedule another follow-up (if count < MAX_FOLLOW_UPS)
            if follow_up_info["follow_up_count"] < MAX_FOLLOW_UPS:
                # Schedule next follow-up
                now = datetime.now()
                next_follow_up_time = now + timedelta(hours=FOLLOW_UP_DELAY_HOURS)
                follow_up_info["follow_up_at"] = next_follow_up_time
                follow_up_info["follow_up_sent"] = False  # Reset so next one can be sent
                follow_up_info["reply_deadline"] = now + timedelta(minutes=REPLY_WAIT_MINUTES)
                print(f"[FollowUpScheduler]  Next follow-up (#{follow_up_info['follow_up_count'] + 1}) scheduled for {next_follow_up_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                # Maximum follow-ups reached - remove from pending
                print(f"[FollowUpScheduler] ⛔ Maximum follow-ups ({MAX_FOLLOW_UPS}) reached. No more follow-ups for {recipient_name}.")
                if chat_id in self.pending_follow_ups:
                    del self.pending_follow_ups[chat_id]
            
            self._save_data()
            
            log_action("follow_up_sent", {
                "chat_id": chat_id,
                "recipient": recipient_name,
                "recipient_phone": recipient_phone,
                "original_message": original_message,
                "follow_up_message": follow_up_message,
                "success": True
            })
            
            print(f"[FollowUpScheduler] [OK] Follow-up sent to {recipient_name} ({recipient_phone})")
            
        except Exception as e:
            print(f"[FollowUpScheduler] [ERROR] Error sending follow-up: {e}")
            import traceback
            traceback.print_exc()
            
            log_action("follow_up_sent", {
                "chat_id": chat_id,
                "recipient": recipient_name,
                "recipient_phone": recipient_phone,
                "success": False,
                "error": str(e)
            })
    
    def check_and_send_follow_ups(self):
        """Check for follow-ups that need to be sent."""
        now = datetime.now()
        follow_ups_to_send = []
        
        if not self.pending_follow_ups:
            return  # No pending follow-ups
        
        print(f"[FollowUpScheduler]  Checking {len(self.pending_follow_ups)} pending follow-ups...")
        
        for chat_id, follow_up_info in list(self.pending_follow_ups.items()):
            # Check if reply was already received
            if follow_up_info.get("reply_received", False):
                print(f"[FollowUpScheduler] [OK] Reply already received for chat {chat_id}, removing from pending")
                del self.pending_follow_ups[chat_id]
                continue
            
            # Check if we've passed the reply deadline
            reply_deadline = follow_up_info.get("reply_deadline")
            if isinstance(reply_deadline, str):
                reply_deadline = datetime.fromisoformat(reply_deadline)
            
            recipient_name = follow_up_info.get("recipient_name", "Unknown")
            sent_at = follow_up_info.get("sent_at")
            if isinstance(sent_at, str):
                sent_at = datetime.fromisoformat(sent_at)
            
            # Calculate time since message was sent
            time_since_sent = (now - sent_at).total_seconds() / 60  # minutes
            
            # Check if we've passed the reply deadline (REPLY_WAIT_MINUTES)
            if now >= reply_deadline:
                # Check if it's time to send the follow-up
                follow_up_at = follow_up_info.get("follow_up_at")
                if isinstance(follow_up_at, str):
                    follow_up_at = datetime.fromisoformat(follow_up_at)
                
                time_until_follow_up = (follow_up_at - now).total_seconds() / 60  # minutes
                
                print(f"[FollowUpScheduler]  Chat {chat_id} ({recipient_name}): "
                      f"Sent {time_since_sent:.1f} min ago, "
                      f"Follow-up in {time_until_follow_up:.1f} min, "
                      f"Already sent: {follow_up_info.get('follow_up_sent', False)}")
                
                if now >= follow_up_at and not follow_up_info.get("follow_up_sent", False):
                    print(f"[FollowUpScheduler]  Time to send follow-up to {recipient_name}!")
                    follow_ups_to_send.append(follow_up_info)
            else:
                # Still waiting for reply deadline
                time_until_deadline = (reply_deadline - now).total_seconds() / 60  # minutes
                print(f"[FollowUpScheduler] ⏳ Chat {chat_id} ({recipient_name}): "
                      f"Still waiting for reply (deadline in {time_until_deadline:.1f} min)")
        
        # Send follow-ups
        if follow_ups_to_send:
            print(f"[FollowUpScheduler] 📤 Sending {len(follow_ups_to_send)} follow-up(s)...")
            for follow_up_info in follow_ups_to_send:
                self.send_follow_up(follow_up_info)
        else:
            print(f"[FollowUpScheduler] [OK] No follow-ups to send at this time")
    
    def run_loop(self):
        """Main loop for checking and sending follow-ups."""
        print("[FollowUpScheduler]  Starting follow-up scheduler...")
        self.running = True
        
        while self.running:
            try:
                self.check_and_send_follow_ups()
                time.sleep(30)  # Check every 30 seconds
            
            except KeyboardInterrupt:
                print("[FollowUpScheduler] Stopping follow-up scheduler...")
                break
            except Exception as e:
                print(f"[FollowUpScheduler] [ERROR] Error in follow-up loop (will retry): {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)
    
    def start(self):
        """Start the follow-up scheduler in a background thread."""
        if self.running:
            print("[FollowUpScheduler] Already running")
            return
        
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        print("[FollowUpScheduler] [OK] Started in background thread")
    
    def stop(self):
        """Stop the follow-up scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[FollowUpScheduler] ⏹️ Stopped")

# Global scheduler instance
_scheduler: Optional[FollowUpScheduler] = None

def get_scheduler(send_message_callback: Optional[Callable] = None) -> FollowUpScheduler:
    """Get or create the global follow-up scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = FollowUpScheduler(send_message_callback)
    return _scheduler

def start_follow_up_scheduler(send_message_callback: Optional[Callable] = None):
    """Start the follow-up scheduler."""
    scheduler = get_scheduler(send_message_callback)
    scheduler.start()

def stop_follow_up_scheduler():
    """Stop the follow-up scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()

def track_sent_message(
    chat_id: str,
    recipient_phone: str,
    recipient_name: str,
    message_text: str,
    original_chat_id: Optional[str] = None
):
    """Track a message sent to a friend."""
    scheduler = get_scheduler()
    scheduler.track_sent_message(chat_id, recipient_phone, recipient_name, message_text, original_chat_id)

def check_for_reply(chat_id: str, sender_phone: str) -> bool:
    """Check if a reply was received for a tracked message."""
    scheduler = get_scheduler()
    return scheduler.check_for_reply(chat_id, sender_phone)

