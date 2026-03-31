"""Abstract adapter interface for messaging platforms."""

import abc


class Message:
    """Normalized message from any platform."""

    __slots__ = ("id", "sender", "text", "timestamp", "raw")

    def __init__(self, id, sender, text, timestamp, raw=None):
        self.id = id
        self.sender = sender
        self.text = text
        self.timestamp = timestamp
        self.raw = raw

    def to_dict(self):
        return {
            "id": self.id,
            "sender": self.sender,
            "text": self.text,
            "timestamp": self.timestamp,
        }


class BaseAdapter(abc.ABC):
    """Interface that all platform adapters must implement."""

    @abc.abstractmethod
    def poll(self):
        """Poll for new messages.

        Returns:
            list[Message]: new messages since last poll
        """

    @abc.abstractmethod
    def send(self, text):
        """Send a message to the channel.

        Args:
            text: message body string
        """

    def setup(self, cfg):
        """Optional setup hook called once before polling starts.

        Args:
            cfg: dict of COCONUT_* config values
        """

    def teardown(self):
        """Optional cleanup hook called on shutdown."""
