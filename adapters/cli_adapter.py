"""CLI adapter — stdin/stdout for testing.

Reads lines from stdin (or a pipe), outputs responses to stdout.
Non-blocking: returns empty list if no input available.
"""
import select
import sys
import time

from adapters.base import BaseAdapter, Message


class CLIAdapter(BaseAdapter):
    """Interactive CLI adapter for testing coconut locally."""

    name = 'cli'

    def __init__(self, config):
        super().__init__(config)
        self._seen = set()

    def poll(self):
        """Read a line from stdin if available (non-blocking)."""
        # On Windows, select doesn't work on stdin — use a simple approach
        if hasattr(select, 'select') and sys.platform != 'win32':
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if not ready:
                return []
        else:
            # Windows: check if stdin has data (works for pipes)
            if sys.stdin.isatty():
                return []  # Skip in interactive mode during poll loop
            # For pipes, just try to read
            pass

        try:
            line = sys.stdin.readline()
        except (EOFError, OSError):
            return []

        if not line:
            return []

        text = line.strip()
        if not text:
            return []

        msg = Message(
            message_id=Message.make_id(text, 'cli-user'),
            sender='cli-user',
            text=text,
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        )
        return [msg]

    def send(self, text):
        """Write response to stdout."""
        formatted = self.format_outbound(text)
        print(formatted, flush=True)
