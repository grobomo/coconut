"""Per-adapter rate limiter — sliding window counter.

Prevents LLM cost runaway by limiting how many messages get classified/replied
per adapter within a configurable time window.

Config (env vars):
  COCONUT_RATE_LIMIT_WINDOW   — window size in seconds (default 60)
  COCONUT_RATE_LIMIT_MAX      — max replies per window per adapter (default 10)
  COCONUT_RATE_LIMIT_ENABLED  — enable/disable (default true)
"""
import time


class RateLimiter:
    """Sliding window rate limiter, keyed by adapter name."""

    def __init__(self, window_seconds=60, max_per_window=10, enabled=True):
        self.window = window_seconds
        self.max = max_per_window
        self.enabled = enabled
        self._events = {}  # adapter_name -> list of timestamps

    def allow(self, adapter_name):
        """Check if a reply is allowed for this adapter. Returns True if allowed."""
        if not self.enabled:
            return True

        now = time.time()
        cutoff = now - self.window

        events = self._events.setdefault(adapter_name, [])
        # Prune expired events
        events[:] = [t for t in events if t > cutoff]

        if len(events) >= self.max:
            return False

        events.append(now)
        return True

    def remaining(self, adapter_name):
        """How many replies are left in the current window."""
        if not self.enabled:
            return self.max

        now = time.time()
        cutoff = now - self.window
        events = self._events.get(adapter_name, [])
        active = sum(1 for t in events if t > cutoff)
        return max(0, self.max - active)

    def stats(self):
        """Return rate limit stats for all adapters."""
        now = time.time()
        cutoff = now - self.window
        result = {}
        for name, events in self._events.items():
            active = sum(1 for t in events if t > cutoff)
            result[name] = {
                'used': active,
                'remaining': max(0, self.max - active),
                'window_seconds': self.window,
                'max_per_window': self.max,
            }
        return result
