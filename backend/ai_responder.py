"""AI response generation with multilingual support."""
from openai import OpenAI
from language_detector import get_language_name
from messaging_rules import get_non_hallucination_response, enforce_context_usage_only

# Conversation history per chat
conversation_history = {}

# User language preferences (chat_id -> language_code)
user_languages = {}

def generate_response(user_message: str, chat_id: str, sender: str, analysis: dict, ai_client: OpenAI) -> str:
    """Generate AI response using OpenAI with enhanced context and multilingual support."""
    if not ai_client:
        return f"You said: {user_message}"
    
    # Get or initialize conversation history
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    
    # Detect or get user's language preference
    detected_lang = analysis.get("language", "en") if analysis else "en"
    user_lang = user_languages.get(chat_id, detected_lang)
    
    # Store language preference
    if detected_lang != "en" or chat_id not in user_languages:
        user_languages[chat_id] = detected_lang
    
    lang_name = get_language_name(user_lang)
    
    # Identify the main topic from conversation history BEFORE building prompt
    history = conversation_history[chat_id]
    topic_keywords = []
    for msg in history:
        text = (msg.get("content") or msg.get("text", "")).lower()
        # Extract potential topics
        if any(word in text for word in ["hospital", "doctor", "medical", "clinic", "emergency", "health", "patient"]):
            topic_keywords.append("medical/healthcare")
        if any(word in text for word in ["restaurant", "food", "dining", "eat", "meal", "cuisine"]):
            topic_keywords.append("restaurants/food")
        if any(word in text for word in ["hotel", "accommodation", "stay", "lodging"]):
            topic_keywords.append("accommodation")
        if any(word in text for word in ["tourist", "sightseeing", "attraction", "visit", "travel", "tour"]):
            topic_keywords.append("tourism")
    
    # Also check current message
    current_text = user_message.lower()
    if any(word in current_text for word in ["hospital", "doctor", "medical", "clinic", "emergency", "health", "patient"]):
        topic_keywords.append("medical/healthcare")
    if any(word in current_text for word in ["restaurant", "food", "dining", "eat", "meal", "cuisine"]):
        topic_keywords.append("restaurants/food")
    if any(word in current_text for word in ["hotel", "accommodation", "stay", "lodging"]):
        topic_keywords.append("accommodation")
    if any(word in current_text for word in ["tourist", "sightseeing", "attraction", "visit", "travel", "tour"]):
        topic_keywords.append("tourism")
    
    # Determine primary topic
    from collections import Counter
    topic_counts = Counter(topic_keywords)
    primary_topic = topic_counts.most_common(1)[0][0] if topic_counts else None
    
    system_prompt = f"""You are a helpful and friendly AI assistant. Be concise and conversational, suitable for text messaging. 
IMPORTANT: Respond in {lang_name} ({user_lang}).

KNOWLEDGE & INFORMATION:
- You have access to general knowledge and can answer questions using your training data
- Use conversation history as context when relevant, but you can also use your general knowledge
- For questions requiring current information (like "find a hospital nearby", "search online"), provide helpful responses based on your knowledge
- Only say "I cannot find that information" if you genuinely don't know the answer from any source
- Be realistic and helpful - if someone asks for a hospital nearby, provide general guidance even if you don't have their exact location

CONTEXT AWARENESS & TOPIC ADHERENCE:
You have access to the COMPLETE conversation history below. Use it to understand context and maintain conversation flow.

CONTEXT USAGE RULES:
1. Read and understand the ENTIRE conversation history from start to finish - EVERY message matters
2. Identify the CURRENT TOPIC being discussed - stick to that topic, don't change subjects
3. When a location is mentioned (e.g., "NYC", "New York"), understand WHY it's mentioned:
   - If user asks "hospital in NYC" → They want HOSPITAL info, not tourist info
   - If user asks "restaurant in NYC" → They want RESTAURANT info, not tourist info
   - The location is CONTEXT for the actual topic (hospital, restaurant, etc.)
4. Don't make assumptions - if user says "NYC" and asks about hospitals, they want HOSPITALS, not tourism
5. Remember ALL topics, facts, preferences, and information shared throughout the conversation
6. When the user references something (e.g., "that thing we discussed", "earlier", "remember when"), search the FULL history to find it
7. Maintain continuity - reference specific messages, topics, or details from earlier in the conversation
8. Build on previous exchanges - don't treat each message in isolation
9. If asked about something mentioned earlier, quote or reference the exact context from the history
10. Show you remember the conversation by naturally referencing past topics
11. STAY ON TOPIC - if the conversation is about hospitals, keep it about hospitals. Don't switch to tourism, restaurants, etc. unless explicitly asked
12. For general knowledge questions (like "find a hospital nearby", "suggest restaurants"), use your knowledge to provide helpful, realistic answers

TOPIC ADHERENCE EXAMPLES:
- User: "I need a hospital in NYC" → Topic: HOSPITALS, Location: NYC → Respond about HOSPITALS in NYC using your knowledge
- User: "I fell from stairs, suggest me a hospital nearby" → Provide helpful guidance about finding hospitals, ask for location if needed
- User: "NYC restaurants" → Topic: RESTAURANTS, Location: NYC → Respond about RESTAURANTS in NYC
- User: "NYC" (after asking about hospitals) → Topic: STILL HOSPITALS, Location: NYC → Continue about HOSPITALS

The conversation history below provides context. Use it to maintain conversation flow, but feel free to use your general knowledge to answer questions realistically and helpfully."""
    
    # Add topic awareness if topic detected
    if primary_topic:
        system_prompt += f"\n\nCURRENT CONVERSATION TOPIC: {primary_topic.upper()}\nStay focused on this topic. If user mentions a location (like NYC), it's context FOR THIS TOPIC, not a topic change. Don't assume location = tourism. If topic is hospitals and user says NYC, they want HOSPITALS in NYC, not tourist attractions."
    
    # Add context based on sentiment/intent
    if analysis:
        sentiment = analysis.get("sentiment", "neutral")
        intent = analysis.get("intent", "general")
        urgency = analysis.get("urgency", "medium")
        
        if sentiment == "negative":
            system_prompt += "\n- The user seems frustrated - be empathetic and helpful."
        elif sentiment == "positive":
            system_prompt += "\n- The user is in a good mood - be warm and friendly."
        
        if urgency == "high":
            system_prompt += "\n- This seems urgent - respond quickly and directly."
        
        if intent == "question":
            system_prompt += "\n- Answer their question clearly, using context from the conversation."
        elif intent == "complaint":
            system_prompt += "\n- Acknowledge their concern and offer solutions based on conversation history."
    
    # Build messages with FULL conversation history as few-shot examples
    messages = [{"role": "system", "content": system_prompt}]
    
    # Use conversation history as few-shot examples to maintain context
    history_to_use = conversation_history[chat_id]
    
    # For very long conversations (200+ messages), use intelligent context windowing:
    # - Keep first 10 messages (conversation foundation and examples)
    # - Keep last 150 messages (recent context and examples)
    if len(history_to_use) > 200:
        # For extremely long conversations, preserve key context
        history_to_use = (
            history_to_use[:10] +  # Conversation start (few-shot examples)
            history_to_use[-150:]  # Recent 150 messages (current context)
        )
    elif len(history_to_use) > 100:
        # For long conversations, keep start + recent
        history_to_use = (
            history_to_use[:10] +  # Conversation start (few-shot examples)
            history_to_use[-90:]   # Recent 90 messages (current context)
        )
    # For conversations < 100 messages, use ALL history (full context as examples)
    
    # Add conversation history as context to maintain conversation flow
    if len(history_to_use) > 0:
        # Add a note about using history for context
        messages.append({
            "role": "system",
            "content": "The following conversation history provides context for this conversation. Use it to understand the conversation flow and maintain continuity. You can also use your general knowledge to answer questions realistically and helpfully."
        })
        
        # Add conversation history as examples
        for msg in history_to_use:
            role = "assistant" if msg.get("role") == "assistant" or msg.get("is_bot") else "user"
            content = msg.get("content") or msg.get("text", "")
            if content:
                messages.append({"role": role, "content": content})
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})
    
    # Add a final reminder about topic adherence if topic detected
    if primary_topic:
        messages.append({
            "role": "system",
            "content": f"REMINDER: The conversation topic is {primary_topic}. If the user mentions a location (like NYC), it's context for {primary_topic}, not a topic change. Stay focused on {primary_topic}."
        })
    
    # Generate response with FULL long context awareness
    # GPT-4o-mini supports 128k tokens - we're using the full conversation history
    response = ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,  # Contains full conversation history for complete context
        temperature=0.7,
        max_tokens=400  # Increased to allow detailed contextual responses that reference history
    )
    
    ai_response = response.choices[0].message.content.strip()
    
    # If message is in any non-English language, ensure response is properly translated
    if user_lang != "en":
        ai_response = ensure_language_translation(ai_response, user_lang, lang_name, ai_client)
    
    # Update history
    conversation_history[chat_id].append({"role": "user", "content": user_message})
    conversation_history[chat_id].append({"role": "assistant", "content": ai_response})
    
    # Keep extensive history for maximum long-term context awareness
    # Store up to 200 messages to maintain very long conversation context
    if len(conversation_history[chat_id]) > 200:
        # For extremely long conversations, preserve:
        # - First 15 messages (conversation foundation and early context)
        # - Last 185 messages (recent and mid-conversation context)
        # This ensures we maintain both early context and recent context
        conversation_history[chat_id] = conversation_history[chat_id][:15] + conversation_history[chat_id][-185:]
    elif len(conversation_history[chat_id]) > 150:
        # For long conversations, keep start + recent
        conversation_history[chat_id] = conversation_history[chat_id][:10] + conversation_history[chat_id][-140:]
    
    return ai_response

def generate_summary(chat_id: str, ai_client: OpenAI) -> str:
    """Generate a comprehensive summary using FULL conversation context."""
    if not ai_client or chat_id not in conversation_history:
        return "No conversation history available."
    
    history = conversation_history[chat_id]
    if len(history) < 2:
        return "Conversation too short to summarize."
    
    # Build conversation text using COMPLETE history for full context awareness
    conv_text = ""
    for i, msg in enumerate(history, 1):  # Use ALL messages with numbering for context
        role = "User" if msg["role"] == "user" else "Assistant"
        conv_text += f"[{i}] {role}: {msg['content']}\n"
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You have access to the COMPLETE conversation history. 
Create a comprehensive summary that:
1. Covers ALL major topics discussed throughout the ENTIRE conversation
2. References key information, decisions, or facts mentioned at any point
3. Shows understanding of the conversation's progression from start to finish
4. Highlights important context that spans multiple messages
Be thorough and show you understand the FULL conversation context."""},
                {"role": "user", "content": f"Complete Conversation History ({len(history)} messages):\n\n{conv_text}\n\nProvide a comprehensive summary:"}
            ],
            temperature=0.5,
            max_tokens=300  # Increased for more comprehensive summaries
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Summary error: {e}"

def get_user_language(chat_id: str) -> str:
    """Get user's preferred language for a chat."""
    return user_languages.get(chat_id, "en")

def ensure_language_translation(text: str, lang_code: str, lang_name: str, ai_client: OpenAI) -> str:
    """Ensure the response is properly translated to the target language if needed."""
    if not ai_client or lang_code == "en":
        return text
    
    try:
        # Use OpenAI to translate/verify the response is in the target language
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are a {lang_name} language expert. Translate the given text to {lang_name} ({lang_code}) if it's not already in {lang_name}. If it's already in {lang_name}, return it as-is. Respond ONLY with the {lang_name} translation, no explanations."},
                {"role": "user", "content": f"Text to translate to {lang_name}: {text}\n\n{lang_name} translation:"}
            ],
            temperature=0.3,
            max_tokens=400
        )
        translated = response.choices[0].message.content.strip()
        print(f"[Translation] Verified/translated to {lang_name} ({lang_code}): {translated[:50]}...")
        return translated
    except Exception as e:
        print(f"[Translation] Error translating to {lang_name}: {e}")
        return text  # Return original if translation fails

