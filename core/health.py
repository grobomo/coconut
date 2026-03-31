"""Health file writer for liveness probes and monitoring.

Writes a JSON health file on each poll cycle so external monitors
(K8s liveness probe, CCC watchdog) can detect if coconut is alive.
"""
import json
import os
import time


# Haiku 4.5 pricing per 1M tokens (USD)
_COST_PER_1M = {'input': 0.80, 'output': 4.00}


def estimate_cost(usage):
    """Estimate USD cost from token usage dict."""
    inp = usage.get('input_tokens', 0)
    out = usage.get('output_tokens', 0)
    return round(inp * _COST_PER_1M['input'] / 1_000_000
                 + out * _COST_PER_1M['output'] / 1_000_000, 6)


class HealthWriter:
    """Writes periodic health status to a JSON file."""

    def __init__(self, data_dir='data', stale_seconds=300):
        self.health_file = os.path.join(data_dir, 'health.json')
        self.stale_seconds = stale_seconds
        self.processed = 0
        self.errors = 0
        self.polls = 0
        self.adapter_stats = {}
        self.started_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    def record_poll(self, adapter_name, message_count=0):
        """Record a poll from an adapter."""
        self.polls += 1
        stats = self.adapter_stats.setdefault(adapter_name, {
            'polls': 0, 'messages': 0, 'errors': 0,
        })
        stats['polls'] += 1
        stats['messages'] += message_count

    def record_adapter_error(self, adapter_name):
        """Record an error for a specific adapter."""
        self.errors += 1
        stats = self.adapter_stats.setdefault(adapter_name, {
            'polls': 0, 'messages': 0, 'errors': 0,
        })
        stats['errors'] += 1

    def update(self, extra=None):
        """Write health file with current stats."""
        now = time.time()
        started_epoch = self._parse_ts(self.started_at)
        uptime_seconds = int(now - started_epoch) if started_epoch else 0

        usage = (extra or {}).get('usage', {})
        cost_usd = estimate_cost(usage)

        health = {
            'status': 'running',
            'last_heartbeat': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'last_heartbeat_epoch': int(now),
            'started_at': self.started_at,
            'uptime_seconds': uptime_seconds,
            'processed': self.processed,
            'errors': self.errors,
            'polls': self.polls,
            'adapters': dict(self.adapter_stats),
            'usage': usage,
            'cost_usd': cost_usd,
        }
        if extra:
            health.update(extra)

        os.makedirs(os.path.dirname(self.health_file), exist_ok=True)
        with open(self.health_file, 'w') as f:
            json.dump(health, f, indent=2)

    @staticmethod
    def _parse_ts(ts_str):
        """Parse ISO timestamp to epoch. Returns 0 on failure."""
        try:
            import calendar
            t = time.strptime(ts_str, '%Y-%m-%dT%H:%M:%SZ')
            return calendar.timegm(t)
        except (ValueError, TypeError):
            return 0

    def check(self):
        """Check health for liveness probe. Returns 0=healthy, 1=stale."""
        try:
            with open(self.health_file) as f:
                health = json.load(f)
            age = time.time() - health.get('last_heartbeat_epoch', 0)
            return 0 if age < self.stale_seconds else 1
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return 1
