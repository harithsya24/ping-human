"""Contact groups and tags management."""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from threading import Lock

GROUPS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contact_groups.json")
_groups_lock = Lock()

def _load_groups() -> Dict:
    """Load groups from file."""
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"groups": [], "tags": {}}
    return {"groups": [], "tags": {}}

def _save_groups(data: Dict):
    """Save groups to file."""
    try:
        with open(GROUPS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[ContactGroups] Error saving: {e}")

def create_group(name: str, description: Optional[str] = None, color: Optional[str] = None) -> Dict:
    """Create a new contact group."""
    with _groups_lock:
        data = _load_groups()
        
        group = {
            "id": f"group_{len(data.get('groups', [])) + 1}",
            "name": name,
            "description": description or "",
            "color": color or "#6366f1",
            "contacts": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        if "groups" not in data:
            data["groups"] = []
        
        data["groups"].append(group)
        _save_groups(data)
        
        return group

def add_contact_to_group(group_id: str, contact_id: str) -> bool:
    """Add a contact to a group."""
    with _groups_lock:
        data = _load_groups()
        
        for group in data.get("groups", []):
            if group.get("id") == group_id:
                if contact_id not in group.get("contacts", []):
                    group["contacts"].append(contact_id)
                    group["updated_at"] = datetime.now().isoformat()
                    _save_groups(data)
                    return True
                return True
        
        return False

def remove_contact_from_group(group_id: str, contact_id: str) -> bool:
    """Remove a contact from a group."""
    with _groups_lock:
        data = _load_groups()
        
        for group in data.get("groups", []):
            if group.get("id") == group_id:
                if contact_id in group.get("contacts", []):
                    group["contacts"].remove(contact_id)
                    group["updated_at"] = datetime.now().isoformat()
                    _save_groups(data)
                    return True
        
        return False

def get_group(group_id: str) -> Optional[Dict]:
    """Get a group by ID."""
    data = _load_groups()
    for group in data.get("groups", []):
        if group.get("id") == group_id:
            return group
    return None

def get_all_groups() -> List[Dict]:
    """Get all groups."""
    data = _load_groups()
    return data.get("groups", [])

def delete_group(group_id: str) -> bool:
    """Delete a group."""
    with _groups_lock:
        data = _load_groups()
        
        original_count = len(data.get("groups", []))
        data["groups"] = [g for g in data.get("groups", []) if g.get("id") != group_id]
        _save_groups(data)
        
        return len(data["groups"]) < original_count

def add_tag_to_contact(contact_id: str, tag: str) -> bool:
    """Add a tag to a contact."""
    with _groups_lock:
        data = _load_groups()
        
        if "tags" not in data:
            data["tags"] = {}
        
        if contact_id not in data["tags"]:
            data["tags"][contact_id] = []
        
        if tag not in data["tags"][contact_id]:
            data["tags"][contact_id].append(tag)
            _save_groups(data)
            return True
        
        return False

def remove_tag_from_contact(contact_id: str, tag: str) -> bool:
    """Remove a tag from a contact."""
    with _groups_lock:
        data = _load_groups()
        
        if contact_id in data.get("tags", {}):
            if tag in data["tags"][contact_id]:
                data["tags"][contact_id].remove(tag)
                _save_groups(data)
                return True
        
        return False

def get_contact_tags(contact_id: str) -> List[str]:
    """Get all tags for a contact."""
    data = _load_groups()
    return data.get("tags", {}).get(contact_id, [])

def get_contacts_by_tag(tag: str) -> List[str]:
    """Get all contacts with a specific tag."""
    data = _load_groups()
    contacts = []
    for contact_id, tags in data.get("tags", {}).items():
        if tag in tags:
            contacts.append(contact_id)
    return contacts

def get_all_tags() -> List[str]:
    """Get all unique tags."""
    data = _load_groups()
    tags = set()
    for contact_tags in data.get("tags", {}).values():
        tags.update(contact_tags)
    return sorted(list(tags))

def get_contacts_by_group(group_id: str) -> List[str]:
    """Get all contacts in a group."""
    group = get_group(group_id)
    if group:
        return group.get("contacts", [])
    return []

