"""Slack adapter — polls channels via Web API, replies via chat.postMessage.

Uses Slack Bot Token (xoxb-...) for authentication. Polls conversations.history
for new messages, sends replies to the same channel.

Env vars:
  COCONUT_SLACK_BOT_TOKEN   — Slack bot token (xoxb-...)
  COCONUT_SLACK_CHANNEL_ID  — Channel ID to monitor (C...)
  COCONUT_SLACK_APP_TOKEN   — (unused, reserved for Socket Mode)
"""
import json
import time
import urllib.request
import urllib.error
import urllib.parse

from adapters.base import BaseAdapter, Message

SLACK_API = 'https://slack.com/api'


class SlackAdapter(BaseAdapter):
    """Slack messaging via Web API polling."""

    name = 'slack'

    def __init__(self, config):
        super().__init__(config)
        self.bot_token = config.get('slack_bot_token', '')
        self.channel_id = config.get('slack_channel_id', '')
        self._last_ts = str(time.time())  # Only fetch messages after startup
        self._seen_ts = set()
        self._bot_user_id = ''

    def _api(self, method, params=None, post_data=None):
        """Call Slack Web API method."""
        url = f'{SLACK_API}/{method}'
        if params:
            url += '?' + urllib.parse.urlencode(params)

        if post_data:
            body = json.dumps(post_data).encode()
            req = urllib.request.Request(url, data=body, method='POST')
            req.add_header('Content-Type', 'application/json; charset=utf-8')
        else:
            req = urllib.request.Request(url)

        req.add_header('Authorization', f'Bearer {self.bot_token}')

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        if not result.get('ok'):
            raise RuntimeError(f"Slack API error: {result.get('error', 'unknown')}")
        return result

    def _get_bot_user_id(self):
        """Fetch bot's own user ID to filter self-messages."""
        if self._bot_user_id:
            return self._bot_user_id
        try:
            result = self._api('auth.test')
            self._bot_user_id = result.get('user_id', '')
        except Exception:
            pass
        return self._bot_user_id

    def poll(self):
        """Fetch new messages from Slack channel."""
        try:
            result = self._api('conversations.history', {
                'channel': self.channel_id,
                'oldest': self._last_ts,
                'limit': 20,
            })
        except Exception:
            return []

        bot_id = self._get_bot_user_id()
        messages = []

        for item in reversed(result.get('messages', [])):
            ts = item.get('ts', '')
            if ts in self._seen_ts:
                continue
            self._seen_ts.add(ts)

            # Skip bot's own messages
            user = item.get('user', '')
            if user == bot_id:
                continue

            # Skip subtypes (joins, leaves, topic changes, etc.)
            if item.get('subtype'):
                continue

            text = item.get('text', '').strip()
            if not text:
                continue

            # Resolve user display name
            sender = self._resolve_user(user) if user else 'unknown'

            messages.append(Message(
                message_id=ts,
                sender=sender,
                text=text,
                timestamp=self._ts_to_iso(ts),
                raw=item,
            ))

            # Track latest timestamp for next poll
            if ts > self._last_ts:
                self._last_ts = ts

        # Prune seen set
        if len(self._seen_ts) > 1000:
            sorted_ts = sorted(self._seen_ts)
            self._seen_ts = set(sorted_ts[-500:])

        return messages

    def _resolve_user(self, user_id):
        """Resolve Slack user ID to display name. Falls back to ID."""
        try:
            result = self._api('users.info', {'user': user_id})
            profile = result.get('user', {}).get('profile', {})
            return (profile.get('display_name')
                    or profile.get('real_name')
                    or user_id)
        except Exception:
            return user_id

    def send(self, text):
        """Send a message to the Slack channel."""
        formatted = self.format_outbound(text)
        try:
            self._api('chat.postMessage', post_data={
                'channel': self.channel_id,
                'text': formatted,
            })
        except Exception as e:
            print(f'Slack send error: {e}', flush=True)

    @staticmethod
    def _ts_to_iso(ts):
        """Convert Slack timestamp (epoch.seq) to ISO format."""
        try:
            epoch = float(ts.split('.')[0] if '.' in ts else ts)
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(epoch))
        except (ValueError, TypeError):
            return ''
