"""CLI adapter — stdin/stdout for testing.

Reads lines from stdin (or a pipe), outputs responses to stdout.
Non-blocking: returns empty list if no input available.

Works on both Unix (select) and Windows (msvcrt.kbhit for tty,
threading for pipes).
"""
import sys
import threading
import time

from adapters.base import BaseAdapter, Message


class CLIAdapter(BaseAdapter):
    """Interactive CLI adapter for testing coconut locally."""

    name = 'cli'

    def __init__(self, config):
        super().__init__(config)
        self._queue = []
        self._lock = threading.Lock()
        self._eof = False
        self._reader_started = False

    def _start_pipe_reader(self):
        """Start background thread to read from piped stdin without blocking."""
        if self._reader_started:
            return
        self._reader_started = True

        def reader():
            try:
                for line in sys.stdin:
                    text = line.strip()
                    if text:
                        with self._lock:
                            self._queue.append(text)
            except (EOFError, OSError):
                pass
            finally:
                self._eof = True

        t = threading.Thread(target=reader, daemon=True)
        t.start()

    def poll(self):
        """Read a line from stdin if available (non-blocking)."""
        if sys.stdin.isatty():
            return self._poll_tty()
        else:
            return self._poll_pipe()

    def _poll_tty(self):
        """Non-blocking read from interactive terminal."""
        if sys.platform == 'win32':
            import msvcrt
            if not msvcrt.kbhit():
                return []
        else:
            import select as _select
            ready, _, _ = _select.select([sys.stdin], [], [], 0)
            if not ready:
                return []

        try:
            line = sys.stdin.readline()
        except (EOFError, OSError):
            return []

        text = (line or '').strip()
        if not text:
            return []

        return [Message(
            message_id=Message.make_id(text, 'cli-user'),
            sender='cli-user',
            text=text,
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        )]

    def _poll_pipe(self):
        """Non-blocking read from piped stdin via background thread."""
        self._start_pipe_reader()

        with self._lock:
            lines = list(self._queue)
            self._queue.clear()

        messages = []
        for text in lines:
            messages.append(Message(
                message_id=Message.make_id(text, 'cli-user'),
                sender='cli-user',
                text=text,
                timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            ))
        return messages

    def send(self, text):
        """Write response to stdout."""
        formatted = self.format_outbound(text)
        print(formatted, flush=True)
