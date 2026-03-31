"""Rolling message cache with overflow archiving.

Keeps the most recent N messages in memory. When cache overflows,
oldest messages are archived to a JSON lines file on disk.
"""

import json
import os
import time


class MessageCache:
    """Fixed-size rolling cache for conversation messages."""

    def __init__(self, max_size=50, archive_path=None):
        self._messages = []
        self._max_size = max_size
        self._archive_path = archive_path
        self._seen_ids = set()

    @property
    def messages(self):
        """Return list of cached messages (oldest first)."""
        return list(self._messages)

    def add(self, message):
        """Add a message to the cache. Returns True if new, False if duplicate.

        Args:
            message: dict with at least "sender" and "text" keys.
                     Optional: "timestamp", "id"
        """
        msg_id = message.get("id") or self._make_id(message)
        if msg_id in self._seen_ids:
            return False

        self._seen_ids.add(msg_id)
        if "timestamp" not in message:
            message["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self._messages.append(message)
        self._trim()
        return True

    def recent(self, n=10):
        """Return the most recent n messages."""
        return self._messages[-n:]

    def clear(self):
        """Clear all cached messages."""
        self._messages.clear()
        self._seen_ids.clear()

    def _trim(self):
        """Archive and remove oldest messages if cache exceeds max_size."""
        while len(self._messages) > self._max_size:
            old = self._messages.pop(0)
            self._archive(old)
            old_id = old.get("id") or self._make_id(old)
            self._seen_ids.discard(old_id)

    def _archive(self, message):
        """Append a message to the archive file."""
        if not self._archive_path:
            return
        try:
            os.makedirs(os.path.dirname(self._archive_path), exist_ok=True)
            with open(self._archive_path, "a") as f:
                f.write(json.dumps(message) + "\n")
        except OSError:
            pass

    @staticmethod
    def _make_id(message):
        """Generate a dedup key from message content."""
        sender = message.get("sender", "")
        text = message.get("text", "")
        ts = message.get("timestamp", "")
        return f"{sender}:{ts}:{text[:64]}"
