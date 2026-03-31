"""CLI adapter -- stdin/stdout for testing.

Reads lines from stdin, sends responses to stdout.
Non-blocking poll using select (Unix) or msvcrt (Windows).
"""

import sys
import time
import select

from adapters.base import BaseAdapter, Message


class CLIAdapter(BaseAdapter):
    """stdin/stdout adapter for testing and local development."""

    def __init__(self, cfg):
        self._bot_name = cfg.get("COCONUT_BOT_NAME", "Coconut")
        self._msg_count = 0

    def setup(self, cfg):
        sys.stderr.write(f"[{self._bot_name}] CLI mode -- type messages, Ctrl+C to quit\n")
        sys.stderr.flush()

    def poll(self):
        """Non-blocking read from stdin."""
        messages = []
        # Use select for non-blocking check on Unix
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
        except (OSError, ValueError):
            return []

        if ready:
            line = sys.stdin.readline()
            if not line:
                return []
            line = line.strip()
            if line:
                self._msg_count += 1
                messages.append(Message(
                    id=f"cli-{self._msg_count}",
                    sender="user",
                    text=line,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ))
        return messages

    def send(self, text):
        """Write response to stdout."""
        sys.stdout.write(f"[{self._bot_name}] {text}\n")
        sys.stdout.flush()
