"""Size-based log rotation — stdlib only.

Rotates coconut.log when it exceeds a configurable max size.
Keeps N backup files (coconut.log.1, coconut.log.2, ...).

Config (env vars):
  COCONUT_LOG_MAX_BYTES  — max log size before rotation (default 5MB)
  COCONUT_LOG_BACKUPS    — number of backup files to keep (default 3)
"""
import os


DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5MB
DEFAULT_BACKUPS = 3


class RotatingLog:
    """File-like object that rotates on size threshold."""

    def __init__(self, path, max_bytes=None, backups=None):
        self.path = path
        self.max_bytes = max_bytes or DEFAULT_MAX_BYTES
        self.backups = backups if backups is not None else DEFAULT_BACKUPS
        self._file = None
        self._size = 0
        self._open()

    def _open(self):
        """Open (or reopen) the log file for appending."""
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        self._file = open(self.path, 'a')
        try:
            self._size = os.path.getsize(self.path)
        except OSError:
            self._size = 0

    def write(self, data):
        """Write data, rotating if size threshold exceeded."""
        if self._size + len(data) > self.max_bytes:
            self._rotate()
        self._file.write(data)
        self._size += len(data)

    def flush(self):
        if self._file:
            self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None

    def _rotate(self):
        """Rotate log files: .log -> .log.1 -> .log.2 -> ..."""
        self.close()

        if self.backups <= 0:
            # No backups — just truncate
            if os.path.exists(self.path):
                os.remove(self.path)
            self._open()
            return

        # Remove oldest backup if at limit
        oldest = f'{self.path}.{self.backups}'
        if os.path.exists(oldest):
            os.remove(oldest)

        # Shift existing backups up by one
        for i in range(self.backups - 1, 0, -1):
            src = f'{self.path}.{i}'
            dst = f'{self.path}.{i + 1}'
            if os.path.exists(src):
                os.replace(src, dst)

        # Current log becomes .1
        if os.path.exists(self.path):
            os.replace(self.path, f'{self.path}.1')

        self._open()
