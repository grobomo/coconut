"""Quote chain resolution for threaded conversations.

Teams messages can quote/reply to other messages. This module resolves
the full chain of quoted messages to provide conversation context.
Works with any platform that provides raw message data with attachments.
"""
import json
import re

MAX_CHAIN_DEPTH = 5


def strip_html(html):
    """Strip HTML tags from message body."""
    text = re.sub(r'<attachment[^>]*></attachment>', '', html)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip().replace('&nbsp;', ' ').replace('&amp;', '&')


def extract_teams_quotes(attachments):
    """Extract quoted message references from Teams attachments."""
    quotes = []
    for att in (attachments or []):
        if att.get('contentType') != 'messageReference':
            continue
        try:
            ref = json.loads(att.get('content', '{}'))
        except (json.JSONDecodeError, TypeError):
            continue
        user = ref.get('messageSender', {}).get('user', {})
        quotes.append({
            'message_id': ref.get('messageId', ''),
            'preview': ref.get('messagePreview', ''),
            'sender': user.get('displayName', ''),
        })
    return quotes


def resolve_teams_chain(chat_id, message, graph_get_fn, depth=0):
    """Resolve the full quote chain for a Teams message.

    Args:
        chat_id: Teams chat thread ID
        message: raw Teams message dict
        graph_get_fn: callable that takes a Graph API path, returns JSON

    Returns: list of dicts (oldest first) with text, sender, timestamp
    """
    chain = []
    quotes = extract_teams_quotes(message.get('attachments', []))

    if quotes and depth < MAX_CHAIN_DEPTH:
        for q in quotes:
            mid = q.get('message_id', '')
            if not mid:
                chain.append({
                    'text': q['preview'],
                    'sender': q['sender'],
                    'timestamp': '',
                })
                continue
            try:
                quoted = graph_get_fn(f'/me/chats/{chat_id}/messages/{mid}')
                chain.extend(resolve_teams_chain(
                    chat_id, quoted, graph_get_fn, depth + 1))
            except Exception:
                chain.append({
                    'text': q['preview'],
                    'sender': q['sender'],
                    'timestamp': '',
                })

    body = message.get('body', {}).get('content', '')
    sender_info = message.get('from', {})
    sender = ''
    if sender_info and sender_info.get('user'):
        sender = sender_info['user'].get('displayName', '')

    chain.append({
        'text': strip_html(body),
        'sender': sender,
        'timestamp': message.get('createdDateTime', ''),
    })
    return chain
