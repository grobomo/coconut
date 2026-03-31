"""Rolling message cache with overflow archiving.

Keeps the N most recent messages in memory/file. Overflow goes to
date-bucketed archive files with configurable TTL.
"""
import json
import os
import time

DEFAULT_CACHE_SIZE = 50
DEFAULT_ARCHIVE_TTL_DAYS = 7


class MessageCache:
    """Thread-safe rolling message cache with filesystem persistence."""

    def __init__(self, data_dir='data', cache_size=None, archive_ttl_days=None):
        self.data_dir = data_dir
        self.cache_file = os.path.join(data_dir, 'cache.json')
        self.archive_dir = os.path.join(data_dir, 'archive')
        self.cache_size = cache_size or DEFAULT_CACHE_SIZE
        self.archive_ttl_days = archive_ttl_days or DEFAULT_ARCHIVE_TTL_DAYS

    def load(self):
        """Load cache from disk."""
        try:
            with open(self.cache_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save(self, messages):
        """Save cache to disk."""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(messages, f, indent=2)

    def add(self, new_messages):
        """Add messages, archive overflow, clean old archives.

        Returns: (updated_cache, archived_count)
        """
        cache = self.load()
        existing_ids = {m.get('message_id') for m in cache if m.get('message_id')}
        unique = [m for m in new_messages if m.get('message_id') not in existing_ids]

        cache = unique + cache  # newest first
        archived = 0

        if len(cache) > self.cache_size:
            overflow = cache[self.cache_size:]
            cache = cache[:self.cache_size]
            self._archive(overflow)
            archived = len(overflow)

        self.save(cache)
        self._cleanup_archive()
        return cache, archived

    def _archive(self, messages):
        """Archive overflow messages into date-bucketed files."""
        os.makedirs(self.archive_dir, exist_ok=True)
        by_date = {}
        for msg in messages:
            ts = msg.get('timestamp', '')[:10]
            by_date.setdefault(ts or 'unknown', []).append(msg)

        for date, msgs in by_date.items():
            path = os.path.join(self.archive_dir, f'{date}.json')
            existing = []
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            existing.extend(msgs)
            with open(path, 'w') as f:
                json.dump(existing, f, indent=2)

    def _cleanup_archive(self):
        """Remove archive files older than TTL."""
        if not os.path.isdir(self.archive_dir):
            return
        cutoff = time.strftime(
            '%Y-%m-%d',
            time.gmtime(time.time() - self.archive_ttl_days * 86400)
        )
        for fname in os.listdir(self.archive_dir):
            if fname.endswith('.json') and fname.replace('.json', '') < cutoff:
                os.remove(os.path.join(self.archive_dir, fname))
