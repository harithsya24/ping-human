"""Language detection functionality."""
import json
from openai import OpenAI

def detect_language(text: str, ai_client: OpenAI) -> str:
    """Detect the language of the message."""
    if not ai_client:
        return "en"
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Detect the language of this message. Respond with ONLY the ISO 639-1 language code (e.g., 'en', 'es', 'fr', 'kn', 'hi', 'ta', 'te', 'ml'). IMPORTANT: Accurately detect Indian languages like Kannada (kn), Tamil (ta), Telugu (te), Hindi (hi), Malayalam (ml), etc. If unsure, return 'en'."},
                {"role": "user", "content": f"Message: {text}\n\nLanguage code:"}
            ],
            temperature=0.1,
            max_tokens=10
        )
        lang_code = response.choices[0].message.content.strip().lower()
        # Validate it's a 2-letter code
        if len(lang_code) == 2 and lang_code.isalpha():
            return lang_code
        return "en"
    except Exception as e:
        print(f"[Language] Detection error: {e}")
        return "en"

def get_language_name(lang_code: str) -> str:
    """Get human-readable language name."""
    lang_names = {
        "en": "English", "es": "Spanish", "fr": "French", "de": "German",
        "zh": "Chinese", "ja": "Japanese", "hi": "Hindi", "ar": "Arabic",
        "pt": "Portuguese", "ru": "Russian", "ko": "Korean", "it": "Italian",
        "kn": "Kannada", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam",
        "mr": "Marathi", "gu": "Gujarati", "bn": "Bengali", "pa": "Punjabi",
        "ur": "Urdu", "th": "Thai", "vi": "Vietnamese", "id": "Indonesian",
        "ms": "Malay", "tr": "Turkish", "pl": "Polish", "nl": "Dutch",
        "sv": "Swedish", "da": "Danish", "fi": "Finnish", "no": "Norwegian",
        "he": "Hebrew", "cs": "Czech", "hu": "Hungarian", "ro": "Romanian",
        "el": "Greek", "uk": "Ukrainian", "bg": "Bulgarian", "hr": "Croatian"
    }
    return lang_names.get(lang_code, lang_code.upper())

