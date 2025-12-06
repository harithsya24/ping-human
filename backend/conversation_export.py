"""Conversation export functionality (PDF, JSON, CSV)."""
import json
import csv
import io
from datetime import datetime
from typing import Dict, List, Optional
from conversation_tracker import get_conversation_thread, get_conversation_summary
from ai_responder import conversation_history, user_languages
from analytics import get_analytics

def export_conversation_json(chat_id: str) -> Dict:
    """Export conversation as JSON."""
    thread = get_conversation_thread(chat_id)
    summary = get_conversation_summary(chat_id)
    
    export_data = {
        "chat_id": chat_id,
        "exported_at": datetime.now().isoformat(),
        "language": user_languages.get(chat_id, "en"),
        "summary": summary,
        "messages": thread,
        "message_count": len(thread)
    }
    
    return export_data

def export_conversation_csv(chat_id: str) -> str:
    """Export conversation as CSV."""
    thread = get_conversation_thread(chat_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Timestamp", "Sender", "Is Bot", "Message", "Message ID"])
    
    for msg in thread:
        writer.writerow([
            msg.get("timestamp", ""),
            msg.get("sender", ""),
            "Yes" if msg.get("is_bot") else "No",
            msg.get("text", ""),
            msg.get("message_id", "")
        ])
    
    return output.getvalue()

def export_conversation_pdf(chat_id: str) -> bytes:
    """Export conversation as PDF."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError:
        raise ImportError("reportlab is required for PDF export. Install with: pip install reportlab")
    
    thread = get_conversation_thread(chat_id)
    summary = get_conversation_summary(chat_id)
    language = user_languages.get(chat_id, "en")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#6366f1'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#4f46e5'),
        spaceAfter=12
    )
    
    normal_style = styles['Normal']
    
    story.append(Paragraph("Conversation Export", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(f"<b>Chat ID:</b> {chat_id}", normal_style))
    story.append(Paragraph(f"<b>Language:</b> {language.upper()}", normal_style))
    story.append(Paragraph(f"<b>Message Count:</b> {len(thread)}", normal_style))
    story.append(Paragraph(f"<b>Exported At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    story.append(Spacer(1, 0.2*inch))
    
    if summary:
        story.append(Paragraph("Summary", heading_style))
        story.append(Paragraph(summary.get("summary", "No summary available"), normal_style))
        story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Messages", heading_style))
    story.append(Spacer(1, 0.1*inch))
    
    for msg in thread:
        timestamp = msg.get("timestamp", "")
        sender = msg.get("sender", "Unknown")
        is_bot = msg.get("is_bot", False)
        text = msg.get("text", "")
        
        sender_label = "Bot" if is_bot else sender
        color = colors.HexColor('#6366f1') if is_bot else colors.HexColor('#1f2937')
        
        sender_style = ParagraphStyle(
            'SenderStyle',
            parent=normal_style,
            fontSize=10,
            textColor=color,
            fontName='Helvetica-Bold'
        )
        
        story.append(Paragraph(f"<b>{sender_label}</b> ({timestamp})", sender_style))
        story.append(Paragraph(text.replace('\n', '<br/>'), normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def export_all_conversations_json() -> Dict:
    """Export all conversations as JSON."""
    all_conversations = {}
    
    for chat_id in conversation_history.keys():
        all_conversations[chat_id] = export_conversation_json(chat_id)
    
    return {
        "exported_at": datetime.now().isoformat(),
        "total_conversations": len(all_conversations),
        "conversations": all_conversations
    }

