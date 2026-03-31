"""Signal adapter — uses signal-cli REST API.

Requires signal-cli-rest-api running (e.g. via Docker):
  docker run -p 8080:8080 bbernhard/signal-cli-rest-api

Env vars:
  COCONUT_SIGNAL_CLI_URL     — API base URL (default http://localhost:8080)
  COCONUT_SIGNAL_GROUP_ID    — group ID to monitor
  COCONUT_SIGNAL_PHONE_NUMBER — registered phone number
"""
import json
import time
import urllib.request
import urllib.error

from adapters.base import BaseAdapter, Message


class SignalAdapter(BaseAdapter):
    """Signal messaging via signal-cli REST API."""

    name = 'signal'

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.get('signal_cli_url', 'http://localhost:8080')
        self.group_id = config.get('signal_group_id', '')
        self.phone = config.get('signal_phone', '')
        self._seen_timestamps = set()

    def poll(self):
        """Receive new messages from signal-cli API."""
        url = f'{self.base_url}/v1/receive/{self.phone}'
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return []

        messages = []
        for envelope in data:
            msg_data = envelope.get('envelope', envelope)
            data_msg = msg_data.get('dataMessage', {})

            # Filter to our group
            group_info = data_msg.get('groupInfo', {})
            if self.group_id and group_info.get('groupId') != self.group_id:
                continue

            text = data_msg.get('message', '')
            if not text:
                continue

            ts = msg_data.get('timestamp', int(time.time() * 1000))
            if ts in self._seen_timestamps:
                continue
            self._seen_timestamps.add(ts)

            sender = msg_data.get('sourceName', msg_data.get('sourceNumber', '?'))
            messages.append(Message(
                message_id=str(ts),
                sender=sender,
                text=text,
                timestamp=time.strftime(
                    '%Y-%m-%dT%H:%M:%SZ',
                    time.gmtime(ts / 1000)
                ),
                raw=msg_data,
            ))

        # Prune seen set (keep last 1000)
        if len(self._seen_timestamps) > 1000:
            sorted_ts = sorted(self._seen_timestamps)
            self._seen_timestamps = set(sorted_ts[-500:])

        return messages

    def send(self, text):
        """Send a message to the Signal group."""
        formatted = self.format_outbound(text)
        url = f'{self.base_url}/v2/send'
        payload = json.dumps({
            'message': formatted,
            'number': self.phone,
            'recipients': [self.group_id],
        }).encode()

        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except (urllib.error.URLError, OSError) as e:
            print(f'Signal send error: {e}', flush=True)
