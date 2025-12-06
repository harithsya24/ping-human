"""Email client for sending emails to contacts."""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, List
from dotenv import load_dotenv

load_dotenv()

# Email configuration from environment variables
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # App password for Gmail
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USERNAME)
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "PingHumans Bot")

def send_email(
    to_email: str,
    subject: str,
    body: str,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None
) -> Dict:
    """
    Send an email to a contact.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text email body
        body_html: Optional HTML email body
        from_email: Sender email (defaults to EMAIL_FROM)
        from_name: Sender name (defaults to EMAIL_FROM_NAME)
    
    Returns:
        Dict with success status and message
    """
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        return {
            "success": False,
            "error": "Email credentials not configured. Please set EMAIL_USERNAME and EMAIL_PASSWORD in .env"
        }
    
    if not to_email or not to_email.strip():
        return {
            "success": False,
            "error": "Recipient email address is required"
        }
    
    from_email = from_email or EMAIL_FROM
    from_name = from_name or EMAIL_FROM_NAME
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = to_email
        
        # Add plain text part
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)
        
        # Add HTML part if provided
        if body_html:
            html_part = MIMEText(body_html, 'html')
            msg.attach(html_part)
        
        # Connect to SMTP server and send
        print(f"[Email] Connecting to {SMTP_SERVER}:{SMTP_PORT}")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Enable encryption
            print(f"[Email] Logging in as {EMAIL_USERNAME}")
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            print(f"[Email] Sending email to {to_email}")
            server.send_message(msg)
        
        print(f"[Email] [OK] Email sent successfully to {to_email}")
        return {
            "success": True,
            "message": f"Email sent to {to_email}",
            "to": to_email,
            "subject": subject
        }
    
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"SMTP authentication failed: {str(e)}"
        print(f"[Email] [ERROR] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "suggestion": "Check your EMAIL_USERNAME and EMAIL_PASSWORD. For Gmail, use an App Password."
        }
    except smtplib.SMTPRecipientsRefused as e:
        error_msg = f"Recipient email rejected: {to_email}"
        print(f"[Email] [ERROR] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "details": str(e)
        }
    except smtplib.SMTPServerDisconnected as e:
        error_msg = f"SMTP server disconnected: {str(e)}"
        print(f"[Email] [ERROR] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "suggestion": "Check SMTP_SERVER and SMTP_PORT settings"
        }
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        print(f"[Email] [ERROR] {error_msg}")
        import traceback
        print(f"[Email] Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": error_msg
        }

def send_email_to_contact(
    contact: Dict,
    subject: str,
    body: str,
    body_html: Optional[str] = None
) -> Dict:
    """
    Send an email to a contact using their email address.
    
    Args:
        contact: Contact dictionary with email field
        subject: Email subject
        body: Plain text email body
        body_html: Optional HTML email body
    
    Returns:
        Dict with success status and message
    """
    # Try to get email from contact
    email = contact.get("email") or contact.get("email_address")
    
    if not email:
        contact_name = contact.get("name") or contact.get("display_name", "Unknown")
        return {
            "success": False,
            "error": f"No email address found for contact: {contact_name}",
            "contact": contact_name
        }
    
    # Clean email (remove "missing value" if present)
    email = email.replace("missing value", "").strip()
    
    if not email or "@" not in email:
        contact_name = contact.get("name") or contact.get("display_name", "Unknown")
        return {
            "success": False,
            "error": f"Invalid email address for contact: {contact_name}",
            "email": email
        }
    
    return send_email(to_email=email, subject=subject, body=body, body_html=body_html)

