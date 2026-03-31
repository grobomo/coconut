#!/usr/bin/env bash
# Test rate limiter — sliding window, per-adapter, burst handling
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "=== Rate Limit Tests ==="

# Test 1: Module imports
echo "Test 1: Rate limiter imports..."
python3 -c "
from core.ratelimit import RateLimiter
print('  PASS: ratelimit imports')
"

# Test 2: Basic allow/deny within window
echo "Test 2: Allow up to max, then deny..."
python3 -c "
from core.ratelimit import RateLimiter

rl = RateLimiter(window_seconds=60, max_per_window=3)

# First 3 should be allowed
assert rl.allow('signal') is True, 'allow 1'
assert rl.allow('signal') is True, 'allow 2'
assert rl.allow('signal') is True, 'allow 3'

# 4th should be denied
assert rl.allow('signal') is False, 'deny 4th'
assert rl.allow('signal') is False, 'deny 5th'

print('  PASS: allows 3, denies 4th+')
"

# Test 3: Per-adapter isolation
echo "Test 3: Per-adapter isolation..."
python3 -c "
from core.ratelimit import RateLimiter

rl = RateLimiter(window_seconds=60, max_per_window=2)

assert rl.allow('signal') is True
assert rl.allow('signal') is True
assert rl.allow('signal') is False  # signal exhausted

# teams should still be allowed
assert rl.allow('teams') is True
assert rl.allow('teams') is True
assert rl.allow('teams') is False  # teams exhausted

print('  PASS: adapters rate-limited independently')
"

# Test 4: Window expiry
echo "Test 4: Window expiry resets counter..."
python3 -c "
import time
from core.ratelimit import RateLimiter

rl = RateLimiter(window_seconds=1, max_per_window=2)

assert rl.allow('test') is True
assert rl.allow('test') is True
assert rl.allow('test') is False

# Wait for window to expire
time.sleep(1.1)

# Should be allowed again
assert rl.allow('test') is True
assert rl.allow('test') is True

print('  PASS: counter resets after window expires')
"

# Test 5: Disabled rate limiter
echo "Test 5: Disabled rate limiter allows all..."
python3 -c "
from core.ratelimit import RateLimiter

rl = RateLimiter(window_seconds=60, max_per_window=1, enabled=False)

# Even with max=1, disabled should allow all
for i in range(100):
    assert rl.allow('test') is True

print('  PASS: disabled limiter allows everything')
"

# Test 6: remaining() accuracy
echo "Test 6: Remaining count..."
python3 -c "
from core.ratelimit import RateLimiter

rl = RateLimiter(window_seconds=60, max_per_window=5)

assert rl.remaining('x') == 5
rl.allow('x')
assert rl.remaining('x') == 4
rl.allow('x')
rl.allow('x')
assert rl.remaining('x') == 2
rl.allow('x')
rl.allow('x')
assert rl.remaining('x') == 0
rl.allow('x')  # denied
assert rl.remaining('x') == 0

print('  PASS: remaining() tracks accurately')
"

# Test 7: stats() output
echo "Test 7: Stats output..."
python3 -c "
from core.ratelimit import RateLimiter

rl = RateLimiter(window_seconds=60, max_per_window=10)
rl.allow('signal')
rl.allow('signal')
rl.allow('teams')

stats = rl.stats()
assert 'signal' in stats
assert 'teams' in stats
assert stats['signal']['used'] == 2
assert stats['signal']['remaining'] == 8
assert stats['teams']['used'] == 1

print('  PASS: stats returns per-adapter usage')
"

# Test 8: Config integration
echo "Test 8: Config includes rate limit fields..."
python3 -c "
import os
os.environ['COCONUT_RATE_LIMIT_ENABLED'] = 'true'
os.environ['COCONUT_RATE_LIMIT_WINDOW'] = '120'
os.environ['COCONUT_RATE_LIMIT_MAX'] = '5'
from core.config import load
cfg = load()
assert cfg['rate_limit_enabled'] is True
assert cfg['rate_limit_window'] == 120
assert cfg['rate_limit_max'] == 5
print('  PASS: rate limit config loaded from env vars')
"

echo ""
echo "=== RATE LIMIT TESTS COMPLETE ==="
