"""AI-powered next message generation and suggestions."""
from openai import OpenAI
from typing import Optional, Dict, List
from conversation_tracker import get_conversation_thread, get_conversation_summary
from contact_manager import get_contact_name
from ai_responder import user_languages
from language_detector import get_language_name

def generate_next_message(
    chat_id: str,
    context: Optional[Dict] = None,
    ai_client: Optional[OpenAI] = None,
    contact_name: Optional[str] = None
) -> str:
    """Generate a suggested next message based on conversation context."""
    if not ai_client:
        return "How can I help you today?"
    
    # Get conversation thread
    thread = get_conversation_thread(chat_id, limit=50)
    summary = get_conversation_summary(chat_id)
    
    # Get user's language preference
    user_lang = user_languages.get(chat_id, "en")
    lang_name = get_language_name(user_lang)
    
    # Build context
    conversation_context = ""
    if thread:
        conversation_context = "\n".join([
            f"{'Bot' if msg.get('is_bot') else 'User'}: {msg['text']}"
            for msg in thread[-10:]  # Last 10 messages
        ])
    
    # Build system prompt
    system_prompt = f"""You are a helpful AI assistant suggesting the next message in a conversation.
Respond in {lang_name} ({user_lang}).

CONTEXT:
- Contact: {contact_name or 'User'}
- Conversation has {summary['message_count']} messages
- Last activity: {summary.get('last_activity', 'N/A')}

TASK:
Based on the conversation history below, suggest the NEXT message the bot should send.
The message should be:
1. Natural and conversational
2. Contextually relevant to the conversation
3. Helpful and engaging
4. Appropriate length for a text message (1-3 sentences)
5. In {lang_name} language

CONVERSATION HISTORY:
{conversation_context if conversation_context else "No previous messages."}

Generate ONLY the suggested message text, nothing else."""
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Suggest the next message to send."}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        suggested_message = response.choices[0].message.content.strip()
        return suggested_message
    except Exception as e:
        print(f"[NextMessage] Error generating suggestion: {e}")
        return "How can I help you today?"

def generate_follow_up_message(
    chat_id: str,
    last_user_message: str,
    ai_client: Optional[OpenAI] = None,
    contact_name: Optional[str] = None
) -> str:
    """Generate a follow-up message after user's last message."""
    if not ai_client:
        return "Thanks for your message! How can I help?"
    
    thread = get_conversation_thread(chat_id, limit=30)
    user_lang = user_languages.get(chat_id, "en")
    lang_name = get_language_name(user_lang)
    
    conversation_context = "\n".join([
        f"{'Bot' if msg.get('is_bot') else 'User'}: {msg['text']}"
        for msg in thread[-8:]
    ])
    
    system_prompt = f"""You are a helpful AI assistant. Generate a follow-up message in {lang_name} ({user_lang}).

The user just sent: "{last_user_message}"

Based on the conversation context, generate an appropriate follow-up message that:
1. Acknowledges their message
2. Provides a helpful response or asks a clarifying question
3. Keeps the conversation engaging
4. Is concise (1-2 sentences)

CONVERSATION CONTEXT:
{conversation_context if conversation_context else "No previous messages."}

Generate ONLY the message text in {lang_name}, nothing else."""
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User said: {last_user_message}\nGenerate a follow-up message."}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[NextMessage] Error generating follow-up: {e}")
        return "Thanks for your message! How can I help?"

def suggest_message_options(
    chat_id: str,
    scenario: str,
    ai_client: Optional[OpenAI] = None,
    contact_name: Optional[str] = None
) -> List[str]:
    """Generate multiple message options for a scenario."""
    if not ai_client:
        return ["How can I help you today?", "Is there anything I can assist with?", "Feel free to reach out anytime!"]
    
    thread = get_conversation_thread(chat_id, limit=20)
    user_lang = user_languages.get(chat_id, "en")
    lang_name = get_language_name(user_lang)
    
    conversation_context = "\n".join([
        f"{'Bot' if msg.get('is_bot') else 'User'}: {msg['text']}"
        for msg in thread[-5:]
    ])
    
    system_prompt = f"""Generate 3 different message options for this scenario in {lang_name} ({user_lang}):

SCENARIO: {scenario}

CONVERSATION CONTEXT:
{conversation_context if conversation_context else "No previous messages."}

Generate 3 distinct message options, each on a new line, numbered 1-3.
Each should be:
- Natural and conversational
- Contextually appropriate
- Different in tone or approach
- Concise (1-2 sentences each)
- In {lang_name} language

Format:
1. [message 1]
2. [message 2]
3. [message 3]"""
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Scenario: {scenario}\nGenerate 3 message options."}
            ],
            temperature=0.8,
            max_tokens=300
        )
        
        text = response.choices[0].message.content.strip()
        # Parse numbered options
        options = []
        for line in text.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove numbering/bullet
                option = line.split(".", 1)[-1].strip()
                if option:
                    options.append(option)
        
        return options[:3] if options else ["How can I help you today?"]
    except Exception as e:
        print(f"[NextMessage] Error generating options: {e}")
        return ["How can I help you today?"]

