"""Message template management."""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from threading import Lock

TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "message_templates.json")
_templates_lock = Lock()

def _load_templates() -> Dict:
    """Load templates from file."""
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"templates": []}
    return {"templates": []}

def _save_templates(data: Dict):
    """Save templates to file."""
    try:
        with open(TEMPLATES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Templates] Error saving: {e}")

def create_template(name: str, content: str, category: str = "general", variables: Optional[List[str]] = None) -> Dict:
    """Create a new message template."""
    with _templates_lock:
        data = _load_templates()
        
        template = {
            "id": f"template_{len(data.get('templates', [])) + 1}",
            "name": name,
            "content": content,
            "category": category,
            "variables": variables or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "usage_count": 0
        }
        
        if "templates" not in data:
            data["templates"] = []
        
        data["templates"].append(template)
        _save_templates(data)
        
        return template

def get_template(template_id: str) -> Optional[Dict]:
    """Get a template by ID."""
    data = _load_templates()
    for template in data.get("templates", []):
        if template.get("id") == template_id:
            return template
    return None

def get_all_templates(category: Optional[str] = None) -> List[Dict]:
    """Get all templates, optionally filtered by category."""
    data = _load_templates()
    templates = data.get("templates", [])
    
    if category:
        templates = [t for t in templates if t.get("category") == category]
    
    return templates

def update_template(template_id: str, name: Optional[str] = None, content: Optional[str] = None, category: Optional[str] = None) -> Optional[Dict]:
    """Update a template."""
    with _templates_lock:
        data = _load_templates()
        
        for template in data.get("templates", []):
            if template.get("id") == template_id:
                if name:
                    template["name"] = name
                if content:
                    template["content"] = content
                if category:
                    template["category"] = category
                
                template["updated_at"] = datetime.now().isoformat()
                _save_templates(data)
                return template
        
        return None

def delete_template(template_id: str) -> bool:
    """Delete a template."""
    with _templates_lock:
        data = _load_templates()
        
        templates = data.get("templates", [])
        original_count = len(templates)
        
        data["templates"] = [t for t in templates if t.get("id") != template_id]
        _save_templates(data)
        
        return len(data["templates"]) < original_count

def render_template(template_id: str, variables: Dict[str, str]) -> Optional[str]:
    """Render a template with variables."""
    template = get_template(template_id)
    if not template:
        return None
    
    content = template.get("content", "")
    
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", value)
    
    with _templates_lock:
        data = _load_templates()
        for t in data.get("templates", []):
            if t.get("id") == template_id:
                t["usage_count"] = t.get("usage_count", 0) + 1
                t["updated_at"] = datetime.now().isoformat()
                _save_templates(data)
                break
    
    return content

def get_template_categories() -> List[str]:
    """Get all template categories."""
    data = _load_templates()
    categories = set()
    for template in data.get("templates", []):
        categories.add(template.get("category", "general"))
    return sorted(list(categories))

