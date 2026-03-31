"""Abstract adapter interface for messaging platforms.

Each adapter implements poll() and send(). The main loop doesn't care
which platform — it just polls and sends through the adapter.
"""
import time
import hashlib


class Message:
    """A normalized message from any platform."""

    __slots__ = ('message_id', 'sender', 'text', 'timestamp', 'raw')

    def __init__(self, message_id, sender, text, timestamp=None, raw=None):
        self.message_id = message_id
        self.sender = sender
        self.text = text
        self.timestamp = timestamp or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        self.raw = raw or {}

    def to_dict(self):
        return {
            'message_id': self.message_id,
            'sender': self.sender,
            'text': self.text,
            'timestamp': self.timestamp,
        }

    @staticmethod
    def make_id(text, sender=''):
        """Generate a deterministic message ID from content."""
        raw = f'{sender}:{text}:{time.time()}'.encode()
        return hashlib.sha256(raw).hexdigest()[:16]


class BaseAdapter:
    """Abstract base for messaging adapters."""

    name = 'base'

    def __init__(self, config):
        self.config = config

    def poll(self):
        """Poll for new messages. Returns list[Message]."""
        raise NotImplementedError

    def send(self, text):
        """Send a message. Text is the formatted response."""
        raise NotImplementedError

    def format_outbound(self, text):
        """Format outbound message with bot identity."""
        cfg = self.config
        emoji = cfg.get('emoji', '\U0001F334')
        name = cfg.get('name', 'Coconut')
        tagline = cfg.get('tagline', '')
        sig = f'{name} ({tagline})' if tagline else name
        return f'{emoji} {text}\n\n\u2014 {sig}'
