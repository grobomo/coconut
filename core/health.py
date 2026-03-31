"""Health file writer for liveness probes and monitoring.

Writes a JSON health file on each poll cycle so external monitors
(K8s liveness probe, CCC watchdog) can detect if coconut is alive.
"""
import json
import os
import time


class HealthWriter:
    """Writes periodic health status to a JSON file."""

    def __init__(self, data_dir='data', stale_seconds=300):
        self.health_file = os.path.join(data_dir, 'health.json')
        self.stale_seconds = stale_seconds
        self.processed = 0
        self.errors = 0
        self.started_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    def update(self, extra=None):
        """Write health file with current stats."""
        health = {
            'status': 'running',
            'last_heartbeat': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'last_heartbeat_epoch': int(time.time()),
            'started_at': self.started_at,
            'processed': self.processed,
            'errors': self.errors,
        }
        if extra:
            health.update(extra)

        os.makedirs(os.path.dirname(self.health_file), exist_ok=True)
        with open(self.health_file, 'w') as f:
            json.dump(health, f, indent=2)

    def check(self):
        """Check health for liveness probe. Returns 0=healthy, 1=stale."""
        try:
            with open(self.health_file) as f:
                health = json.load(f)
            age = time.time() - health.get('last_heartbeat_epoch', 0)
            return 0 if age < self.stale_seconds else 1
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return 1
