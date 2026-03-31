"""Semantic message classifier — uses LLM to analyze conversation context.

Classifies messages as:
  REPLY  — answer directly (questions, status inquiries, help requests)
  RELAY  — route to external system (code tasks, infrastructure work)
  IGNORE — skip (greetings, bot output, off-topic)
"""
import json
from core import llm

MAX_CLASSIFY_CONTEXT = 15

CLASSIFICATION_PROMPT = """You are a message classifier. You receive a JSON array of recent chat messages (oldest first). Each has: sender, text, timestamp.

Classify ONLY messages marked "classify": true. Use surrounding messages as context.

## Classifications

REPLY - Questions or requests the bot should answer directly. Includes: security questions, product questions, status inquiries, help requests, IT admin questions.

RELAY - Tasks for an external system. Code generation, infrastructure changes, deployment requests, PR reviews. Must contain a clear actionable task.

IGNORE - Regular chat, greetings, bot-generated output, empty messages, messages not directed at the bot.

## Rules
- A message quoting another message inherits that context
- Bare mentions with no task and no quoted context = IGNORE
- Questions about the bot itself = REPLY
- "Do X" or "Build Y" or "Fix Z" = RELAY (if it's a code/infra task)
- Security/product questions = REPLY

## Output
Return a JSON array of objects, one per classified message:
[{"message_id": "...", "classification": "REPLY|RELAY|IGNORE", "reason": "brief reason"}]

Return ONLY valid JSON. No markdown, no explanation."""


def classify(messages, api_key, model='claude-haiku-4-5-20251001'):
    """Classify a batch of messages using conversation context.

    Args:
        messages: list of dicts with keys: message_id, sender, text, timestamp,
                  and optionally classify=True for messages to classify
        api_key: Anthropic API key
        model: model to use

    Returns: list of dicts with message_id, classification, reason
    """
    if not messages:
        return []

    # Mark newest messages for classification if not already marked
    to_classify = [m for m in messages if m.get('classify')]
    if not to_classify:
        return []

    # Limit context to most recent N messages to reduce token usage
    context_msgs = messages[-MAX_CLASSIFY_CONTEXT:] if len(messages) > MAX_CLASSIFY_CONTEXT else messages

    prompt = f"{CLASSIFICATION_PROMPT}\n\nMessages:\n{json.dumps(context_msgs, indent=2)}"

    response = llm.chat(
        api_key=api_key,
        system_prompt='You are a message classifier. Return only valid JSON.',
        user_message=prompt,
        model=model,
        max_tokens=256,
    )

    # Parse JSON from response (handle markdown fences)
    text = response.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        text = text.rsplit('```', 1)[0]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [{'message_id': m.get('message_id', ''),
                 'classification': 'IGNORE',
                 'reason': 'classifier parse error'}
                for m in to_classify]
