"""Access macOS Contacts app directly from Python."""
import subprocess
import json
from typing import List, Dict, Optional
from datetime import datetime

def get_contacts_via_applescript() -> List[Dict]:
    """Fetch contacts from macOS Contacts app using AppleScript."""
    applescript = '''
    tell application "Contacts"
        set contactList to {}
        repeat with aPerson in people
            set contactInfo to {}
            set end of contactInfo to "name:" & (first name of aPerson) & " " & (last name of aPerson)
            set end of contactInfo to "organization:" & (organization of aPerson)
            
            -- Get phone numbers
            set phoneNumbers to {}
            repeat with aPhone in phones of aPerson
                set end of phoneNumbers to value of aPhone
            end repeat
            set end of contactInfo to "phones:" & (phoneNumbers as string)
            
            -- Get emails
            set emails to {}
            repeat with anEmail in emails of aPerson
                set end of emails to value of anEmail
            end repeat
            set end of contactInfo to "emails:" & (emails as string)
            
            set end of contactList to contactInfo
        end repeat
        return contactList
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[macOS Contacts] Error: {result.stderr}")
            return []
        
        # Parse the AppleScript output (it's a bit messy, so we'll use a better approach)
        return []
    except subprocess.TimeoutExpired:
        print("[macOS Contacts] Timeout accessing Contacts app")
        return []
    except Exception as e:
        print(f"[macOS Contacts] Error: {e}")
        return []

def get_contacts_via_export() -> List[Dict]:
    """Export contacts to vCard format and parse them."""
    try:
        # Export contacts to vCard format
        result = subprocess.run(
            ['osascript', '-e', '''
                tell application "Contacts"
                    set vcardData to ""
                    repeat with aPerson in people
                        set vcardData to vcardData & (vcard of aPerson) & "\\n"
                    end repeat
                    return vcardData
                end tell
            '''],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[macOS Contacts] Export error: {result.stderr}")
            return []
        
        # Parse vCard format
        contacts = []
        vcard_lines = result.stdout.split('\n')
        current_contact = {}
        
        for line in vcard_lines:
            line = line.strip()
            if line.startswith('BEGIN:VCARD'):
                current_contact = {}
            elif line.startswith('FN:'):
                current_contact['name'] = line[3:].strip()
            elif line.startswith('ORG:'):
                current_contact['organization'] = line[4:].strip()
            elif line.startswith('TEL'):
                phone = line.split(':')[-1].strip()
                if 'phone_numbers' not in current_contact:
                    current_contact['phone_numbers'] = []
                current_contact['phone_numbers'].append(phone)
            elif line.startswith('EMAIL'):
                email = line.split(':')[-1].strip()
                if 'emails' not in current_contact:
                    current_contact['emails'] = []
                current_contact['emails'].append(email)
            elif line.startswith('END:VCARD'):
                if current_contact:
                    contacts.append(current_contact)
                current_contact = {}
        
        return contacts
    except Exception as e:
        print(f"[macOS Contacts] Export error: {e}")
        return []

def get_contacts_simple() -> List[Dict]:
    """Get contacts using a simpler AppleScript approach."""
    applescript = '''
    tell application "Contacts"
        set output to ""
        repeat with aPerson in people
            set fullName to (first name of aPerson) & " " & (last name of aPerson)
            set orgName to organization of aPerson
            
            -- Get first phone number
            set phoneNum to ""
            if (count of phones of aPerson) > 0 then
                set phoneNum to value of item 1 of phones of aPerson
            end if
            
            -- Get first email
            set emailAddr to ""
            if (count of emails of aPerson) > 0 then
                set emailAddr to value of item 1 of emails of aPerson
            end if
            
            set output to output & fullName & "|" & orgName & "|" & phoneNum & "|" & emailAddr & "\\n"
        end repeat
        return output
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[macOS Contacts] Error: {result.stderr}")
            return []
        
        contacts = []
        for line in result.stdout.strip().split('\n'):
            if not line or line.strip() == '':
                continue
            
            parts = line.split('|')
            if len(parts) >= 4:
                name = parts[0].strip()
                organization = parts[1].strip()
                phone = parts[2].strip()
                email = parts[3].strip()
                
                # Clean up "missing value" from AppleScript output
                if name and "missing value" in name.lower():
                    name = name.replace("missing value", "").strip()
                if organization and "missing value" in organization.lower():
                    organization = organization.replace("missing value", "").strip()
                
                # Use organization as name if name is empty or just "missing value"
                if not name or name.lower() == "missing value":
                    if organization:
                        name = organization
                    elif phone:
                        name = phone
                    else:
                        name = "Unknown"
                
                if name or phone:  # Only add if we have at least a name or phone
                    contact = {
                        "name": name if name and name != "Unknown" else (organization if organization else phone),
                        "display_name": name if name and name != "Unknown" else (organization if organization else phone),
                        "phone_number": phone,
                        "organization": organization if organization and "missing value" not in organization.lower() else "",
                        "email": email if email and "missing value" not in email.lower() else "",
                        "source": "macos_contacts",
                        "first_seen": datetime.now().isoformat(),
                        "message_count": 0
                    }
                    
                    # Add metadata for business contacts
                    if organization:
                        contact["metadata"] = {
                            "type": "business",
                            "organization": organization
                        }
                    
                    contacts.append(contact)
        
        return contacts
    except subprocess.TimeoutExpired:
        print("[macOS Contacts] Timeout accessing Contacts app")
        return []
    except Exception as e:
        print(f"[macOS Contacts] Error: {e}")
        return []

def sync_macos_contacts_to_cache():
    """Sync macOS Contacts to our contact cache."""
    from contact_manager import contacts_cache, contact_phone_map, update_contact_info
    
    print("[macOS Contacts] Fetching contacts from macOS Contacts app...")
    macos_contacts = get_contacts_simple()
    
    if not macos_contacts:
        print("[macOS Contacts] No contacts found or access denied")
        return 0
    
    synced_count = 0
    for contact in macos_contacts:
        phone = contact.get("phone_number", "")
        if phone:
            # Normalize phone
            phone_normalized = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            
            # Update or add to cache
            update_contact_info(phone, {
                "name": contact.get("name", ""),
                "display_name": contact.get("display_name", ""),
                "phone_number": phone,
                "organization": contact.get("organization", ""),
                "email": contact.get("email", ""),
                "source": "macos_contacts",
                "metadata": contact.get("metadata", {})
            })
            synced_count += 1
    
    print(f"[macOS Contacts] [OK] Synced {synced_count} contacts from macOS Contacts app")
    return synced_count

if __name__ == "__main__":
    print("=" * 70)
    print(" macOS Contacts Access")
    print("=" * 70)
    
    contacts = get_contacts_simple()
    
    if contacts:
        print(f"\nFound {len(contacts)} contacts:\n")
        for i, contact in enumerate(contacts[:10], 1):  # Show first 10
            print(f"{i}. {contact.get('name', 'Unknown')}")
            if contact.get('phone_number'):
                print(f"   Phone: {contact.get('phone_number')}")
            if contact.get('organization'):
                print(f"   Org: {contact.get('organization')}")
            print()
        
        if len(contacts) > 10:
            print(f"... and {len(contacts) - 10} more contacts")
        
        print(f"\nTotal: {len(contacts)} contacts")
    else:
        print("\nNo contacts found or permission denied.")
        print("\nTo grant permission:")
        print("  System Settings > Privacy & Security > Contacts")
        print("  Enable access for Terminal (or your Python app)")
    
    print("=" * 70)

