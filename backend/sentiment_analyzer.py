"""Sentiment and intent analysis functionality."""
import json
from openai import OpenAI

def analyze_message(text: str, ai_client: OpenAI) -> dict:
    """Analyze message for sentiment, intent, urgency, and language."""
    if not ai_client:
        return {"sentiment": "neutral", "intent": "general", "urgency": "medium", "language": "en"}
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Analyze the message and respond with ONLY valid JSON. No other text."},
                {"role": "user", "content": f"""Analyze this message and return JSON with:
- sentiment: "positive", "neutral", or "negative"
- intent: one word like "question", "greeting", "complaint", "request", "thanks", "general"
- urgency: "low", "medium", or "high"
- language: ISO 639-1 language code (e.g., "en", "es", "fr", "kn", "hi", "ta", "te")

IMPORTANT: Detect the language accurately, including Indian languages like Kannada (kn), Tamil (ta), Telugu (te), Hindi (hi), etc.

Message: {text}"""}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        analysis = json.loads(response.choices[0].message.content)
        return {
            "sentiment": analysis.get("sentiment", "neutral"),
            "intent": analysis.get("intent", "general"),
            "urgency": analysis.get("urgency", "medium"),
            "language": analysis.get("language", "en")
        }
    except Exception as e:
        print(f"[Sentiment] Analysis error: {e}")
        return {"sentiment": "neutral", "intent": "general", "urgency": "medium", "language": "en"}

