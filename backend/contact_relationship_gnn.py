"""Graph Neural Network for contact relationship mapping and inference."""
import json
import os
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.data import Data
    from torch_geometric.nn import GCNConv, GATConv, SAGEConv
    from sklearn.preprocessing import LabelEncoder
    GNN_AVAILABLE = True
except ImportError:
    GNN_AVAILABLE = False
    print("[ContactGNN] PyTorch Geometric not available. Install with: pip install torch torch-geometric")
    # Dummy types for type hints when GNN is not available
    Data = None
    nn = type('nn', (), {'Module': type('Module', (), {})})()

RELATIONSHIPS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contact_relationships.json")

if GNN_AVAILABLE:
    class ContactGNN(nn.Module):
        """Graph Neural Network for contact relationship prediction."""
        
        def __init__(self, num_features: int, hidden_dim: int = 64, num_classes: int = 5):
            super(ContactGNN, self).__init__()
            self.conv1 = GCNConv(num_features, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, hidden_dim)
            self.conv3 = GCNConv(hidden_dim, num_classes)
            self.dropout = nn.Dropout(0.2)
        
        def forward(self, x, edge_index):
            x = F.relu(self.conv1(x, edge_index))
            x = self.dropout(x)
            x = F.relu(self.conv2(x, edge_index))
            x = self.dropout(x)
            x = self.conv3(x, edge_index)
            return F.log_softmax(x, dim=1)
else:
    # Dummy class when GNN is not available
    class ContactGNN:
        def __init__(self, *args, **kwargs):
            pass

def load_relationships() -> Dict:
    """Load contact relationships from file."""
    if os.path.exists(RELATIONSHIPS_FILE):
        try:
            with open(RELATIONSHIPS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"relationships": [], "contacts": {}}
    return {"relationships": [], "contacts": {}}

def save_relationships(data: Dict):
    """Save contact relationships to file."""
    try:
        with open(RELATIONSHIPS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[ContactGNN] Error saving relationships: {e}")

def add_relationship(contact1: str, contact2: str, relationship_type: str, strength: float = 1.0):
    """Add a relationship between two contacts."""
    data = load_relationships()
    
    relationship = {
        "contact1": contact1,
        "contact2": contact2,
        "type": relationship_type,
        "strength": strength,
        "created_at": __import__('datetime').datetime.now().isoformat()
    }
    
    if "relationships" not in data:
        data["relationships"] = []
    
    data["relationships"].append(relationship)
    save_relationships(data)

def get_contact_graph(contacts: List[Dict]):
    """Build a graph from contacts for GNN processing."""
    if not GNN_AVAILABLE or not contacts:
        return None
    
    try:
        relationships_data = load_relationships()
        relationships = relationships_data.get("relationships", [])
        
        contact_map = {}
        for i, contact in enumerate(contacts):
            contact_id = contact.get("phone_number") or contact.get("phone") or contact.get("identifier", str(i))
            contact_map[contact_id] = i
        
        num_contacts = len(contacts)
        if num_contacts == 0:
            return None
        
        edge_index = []
        edge_attr = []
        
        for rel in relationships:
            c1 = rel.get("contact1")
            c2 = rel.get("contact2")
            
            if c1 in contact_map and c2 in contact_map:
                idx1 = contact_map[c1]
                idx2 = contact_map[c2]
                edge_index.append([idx1, idx2])
                edge_index.append([idx2, idx1])
                
                strength = rel.get("strength", 1.0)
                rel_type = rel.get("type", "unknown")
                edge_attr.append([strength, _encode_relationship_type(rel_type)])
                edge_attr.append([strength, _encode_relationship_type(rel_type)])
        
        if not edge_index:
            return None
        
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_attr, dtype=torch.float)
        
        node_features = _extract_node_features(contacts)
        x = torch.tensor(node_features, dtype=torch.float)
        
        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
    
    except Exception as e:
        print(f"[ContactGNN] Error building graph: {e}")
        return None

def _extract_node_features(contacts: List[Dict]) -> List[List[float]]:
    """Extract features for each contact node."""
    features = []
    
    for contact in contacts:
        name = contact.get("name", "") or contact.get("display_name", "")
        
        feature_vector = [
            len(name),
            _has_email(contact),
            _has_phone(contact),
            _is_business(contact),
            _interaction_frequency(contact)
        ]
        
        features.append(feature_vector)
    
    return features

def _has_email(contact: Dict) -> float:
    """Check if contact has email (binary feature)."""
    return 1.0 if contact.get("email") or contact.get("email_address") else 0.0

def _has_phone(contact: Dict) -> float:
    """Check if contact has phone (binary feature)."""
    return 1.0 if contact.get("phone_number") or contact.get("phone") else 0.0

def _is_business(contact: Dict) -> float:
    """Check if contact appears to be a business."""
    name = (contact.get("name", "") or contact.get("display_name", "")).lower()
    business_keywords = ["pizza", "restaurant", "cafe", "shop", "store", "service", "delivery", "guy", "place"]
    return 1.0 if any(kw in name for kw in business_keywords) else 0.0

def _interaction_frequency(contact: Dict) -> float:
    """Get interaction frequency (normalized)."""
    return min(contact.get("interaction_count", 0) / 10.0, 1.0)

def _encode_relationship_type(rel_type: str) -> float:
    """Encode relationship type as numeric."""
    encoding = {
        "family": 1.0,
        "friend": 0.8,
        "colleague": 0.6,
        "service": 0.4,
        "unknown": 0.2
    }
    return encoding.get(rel_type.lower(), 0.2)

def predict_relationships(contacts: List[Dict], model: Optional = None) -> List[Dict]:
    """Use GNN to predict relationships between contacts."""
    if not GNN_AVAILABLE:
        return []
    
    try:
        graph = get_contact_graph(contacts)
        if graph is None:
            return []
        
        if model is None:
            num_features = graph.x.size(1)
            model = ContactGNN(num_features=num_features)
        
        model.eval()
        with torch.no_grad():
            predictions = model(graph.x, graph.edge_index)
        
        predicted_relationships = []
        num_contacts = len(contacts)
        
        for i in range(num_contacts):
            for j in range(i + 1, num_contacts):
                pred_score = predictions[i][j % predictions.size(1)].item()
                
                if pred_score > 0.3:
                    contact1 = contacts[i].get("phone_number") or contacts[i].get("phone", f"contact_{i}")
                    contact2 = contacts[j].get("phone_number") or contacts[j].get("phone", f"contact_{j}")
                    
                    relationship_type = _predict_relationship_type(pred_score)
                    
                    predicted_relationships.append({
                        "contact1": contact1,
                        "contact2": contact2,
                        "type": relationship_type,
                        "confidence": round(pred_score, 3),
                        "predicted": True
                    })
        
        return predicted_relationships
    
    except Exception as e:
        print(f"[ContactGNN] Error predicting relationships: {e}")
        return []

def _predict_relationship_type(score: float) -> str:
    """Predict relationship type from score."""
    if score > 0.8:
        return "family"
    elif score > 0.6:
        return "friend"
    elif score > 0.4:
        return "colleague"
    elif score > 0.2:
        return "service"
    else:
        return "unknown"

def get_contact_communities(contacts: List[Dict]) -> Dict[str, List[str]]:
    """Detect communities/clusters in contact graph using GNN."""
    if not GNN_AVAILABLE:
        return {}
    
    try:
        graph = get_contact_graph(contacts)
        if graph is None:
            return {}
        
        num_features = graph.x.size(1)
        model = ContactGNN(num_features=num_features, hidden_dim=32, num_classes=5)
        
        model.eval()
        with torch.no_grad():
            embeddings = model.conv2(model.conv1(graph.x, graph.edge_index), graph.edge_index)
        
        from sklearn.cluster import KMeans
        embeddings_np = embeddings.numpy()
        
        num_clusters = min(5, len(contacts))
        if num_clusters < 2:
            return {}
        
        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(embeddings_np)
        
        communities = defaultdict(list)
        for i, cluster_id in enumerate(clusters):
            contact_id = contacts[i].get("phone_number") or contacts[i].get("phone", f"contact_{i}")
            contact_name = contacts[i].get("name") or contacts[i].get("display_name", "Unknown")
            communities[f"community_{cluster_id}"].append({
                "id": contact_id,
                "name": contact_name
            })
        
        return dict(communities)
    
    except Exception as e:
        print(f"[ContactGNN] Error detecting communities: {e}")
        return {}

def get_relationship_graph_data(contacts: List[Dict]) -> Dict:
    """Get graph data for visualization."""
    relationships_data = load_relationships()
    relationships = relationships_data.get("relationships", [])
    
    nodes = []
    edges = []
    
    contact_map = {}
    for i, contact in enumerate(contacts):
        contact_id = contact.get("phone_number") or contact.get("phone") or contact.get("identifier", str(i))
        contact_name = contact.get("name") or contact.get("display_name", "Unknown")
        contact_map[contact_id] = i
        
        nodes.append({
            "id": contact_id,
            "label": contact_name,
            "group": _categorize_contact(contact)
        })
    
    for rel in relationships:
        c1 = rel.get("contact1")
        c2 = rel.get("contact2")
        
        if c1 in contact_map and c2 in contact_map:
            edges.append({
                "from": c1,
                "to": c2,
                "label": rel.get("type", "unknown"),
                "value": rel.get("strength", 1.0)
            })
    
    return {
        "nodes": nodes,
        "edges": edges
    }

def _categorize_contact(contact: Dict) -> str:
    """Categorize contact for visualization."""
    name = (contact.get("name", "") or contact.get("display_name", "")).lower()
    
    if any(kw in name for kw in ["pizza", "restaurant", "food", "delivery"]):
        return "service"
    elif any(kw in name for kw in ["doctor", "hospital", "clinic", "medical"]):
        return "healthcare"
    elif any(kw in name for kw in ["work", "office", "company"]):
        return "work"
    else:
        return "personal"

def infer_relationships_from_interactions(contacts: List[Dict], conversation_threads: Dict) -> List[Dict]:
    """Infer relationships from conversation patterns using GNN."""
    if not GNN_AVAILABLE:
        return []
    
    try:
        interaction_graph = defaultdict(lambda: defaultdict(int))
        
        for chat_id, messages in conversation_threads.items():
            senders = set()
            for msg in messages:
                sender = msg.get("sender", "")
                if sender:
                    senders.add(sender)
            
            sender_list = list(senders)
            for i in range(len(sender_list)):
                for j in range(i + 1, len(sender_list)):
                    interaction_graph[sender_list[i]][sender_list[j]] += 1
                    interaction_graph[sender_list[j]][sender_list[i]] += 1
        
        inferred = []
        for contact1, interactions in interaction_graph.items():
            for contact2, count in interactions.items():
                if count >= 3:
                    strength = min(count / 10.0, 1.0)
                    rel_type = "friend" if strength > 0.5 else "acquaintance"
                    
                    inferred.append({
                        "contact1": contact1,
                        "contact2": contact2,
                        "type": rel_type,
                        "strength": strength,
                        "interaction_count": count,
                        "inferred": True
                    })
        
        return inferred
    
    except Exception as e:
        print(f"[ContactGNN] Error inferring relationships: {e}")
        return []

