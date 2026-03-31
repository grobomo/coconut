"""Semantic message classifier.

Takes conversation history, classifies each new message as:
- REPLY: answer directly via LLM
- RELAY: route to external CCC endpoint
- IGNORE: skip (bot's own messages, system noise, etc.)
"""

import json
from core import llm

CLASSIFY_PROMPT = """You are a message classifier for a chat bot named {bot_name}.

Analyze the conversation history and classify the LAST message.

Classification rules:
- REPLY: The message is directed at the bot, asks a question, or warrants a response.
  Examples: questions, greetings, requests for help, @mentions of the bot.
- RELAY: The message asks the bot to do something that requires an external system
  (run a command, check a deployment, query an API). The bot cannot do this directly.
- IGNORE: The message is not directed at the bot, is the bot's own message, is a
  system notification, or is casual chatter between other people that doesn't need
  a response.

Respond with EXACTLY one JSON object:
{{"classification": "REPLY"|"RELAY"|"IGNORE", "reason": "brief reason"}}

Conversation history (most recent last):
{history}

Classify the LAST message only."""


def classify(api_key, model, messages, bot_name="Coconut"):
    """Classify the last message in a conversation.

    Args:
        api_key: Anthropic API key
        model: model ID
        messages: list of {"sender": str, "text": str, "timestamp": str}
        bot_name: name of the bot (to detect self-messages)

    Returns:
        tuple: (classification, reason) where classification is
               "REPLY", "RELAY", or "IGNORE"
    """
    if not messages:
        return ("IGNORE", "empty")

    last = messages[-1]

    # Fast path: skip bot's own messages
    if last.get("sender", "").lower() == bot_name.lower():
        return ("IGNORE", "own message")

    # Build history string for LLM
    history_lines = []
    for msg in messages:
        ts = msg.get("timestamp", "")
        sender = msg.get("sender", "unknown")
        text = msg.get("text", "")
        history_lines.append(f"[{ts}] {sender}: {text}")
    history = "\n".join(history_lines)

    prompt = CLASSIFY_PROMPT.format(bot_name=bot_name, history=history)

    try:
        response = llm.chat(
            api_key=api_key,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=128,
        )
        result = json.loads(response)
        classification = result.get("classification", "IGNORE").upper()
        reason = result.get("reason", "")
        if classification not in ("REPLY", "RELAY", "IGNORE"):
            classification = "IGNORE"
        return (classification, reason)
    except (json.JSONDecodeError, llm.LLMError, KeyError):
        return ("IGNORE", "classification failed")
