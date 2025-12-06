#!/usr/bin/env python3
"""List all contacts with detailed information."""
import json
import sys
import os

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contact_manager import get_all_contacts

def list_all_contacts():
    """List all contacts with full details."""
    contacts = get_all_contacts()
    
    print("=" * 70)
    print(" ALL CONTACTS - DETAILED LIST")
    print("=" * 70)
    print(f"Total contacts: {len(contacts)}\n")
    
    if not contacts:
        print("No contacts found yet.")
        print("\nContacts will be automatically added when:")
        print("  • You receive iMessage messages")
        print("  • Contacts are extracted from chat_handles in Kafka events")
        print("  • You grant contact access permission")
        print("=" * 70)
        return
    
    for i, contact in enumerate(contacts, 1):
        print(f"\n{'─' * 70}")
        print(f"Contact #{i}")
        print(f"{'─' * 70}")
        
        # Basic Info
        print(f"  Name:           {contact.get('name', 'Unknown')}")
        print(f"  Display Name:  {contact.get('display_name', 'Unknown')}")
        print(f"  Phone:          {contact.get('phone_number', 'N/A')}")
        print(f"  Source:         {contact.get('source', 'unknown')}")
        
        # Statistics
        message_count = contact.get('message_count', 0)
        print(f"  Messages:       {message_count}")
        
        # Timestamps
        if contact.get('first_seen'):
            print(f"  First Seen:     {contact.get('first_seen')}")
        if contact.get('last_interaction'):
            print(f"  Last Interaction: {contact.get('last_interaction')}")
        if contact.get('last_updated'):
            print(f"  Last Updated:   {contact.get('last_updated')}")
        
        # Language
        if contact.get('preferred_language'):
            print(f"  Language:       {contact.get('preferred_language')}")
        
        # Last Message
        if contact.get('last_message'):
            last_msg = contact.get('last_message', '')[:100]
            print(f"  Last Message:    {last_msg}{'...' if len(contact.get('last_message', '')) > 100 else ''}")
        
        # Metadata
        if contact.get('metadata'):
            print(f"  Metadata:")
            for key, value in contact.get('metadata', {}).items():
                print(f"    • {key}: {value}")
        
        # Message Context
        if contact.get('message_context'):
            context_count = len(contact.get('message_context', []))
            print(f"  Message Context: {context_count} message(s) stored")
    
    print(f"\n{'─' * 70}")
    print(f"Total: {len(contacts)} contact(s)")
    print("=" * 70)

if __name__ == "__main__":
    list_all_contacts()

