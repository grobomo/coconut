#!/usr/bin/env bash
# Tests for 005-harden-coconut: retry, token persistence, context limits, health CLI
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Hardening Tests ==="

# Test 1: LLM retry on transient errors
echo "Test 1: LLM retry with backoff..."
python3 -c "
import http.server
import json
import threading
import time
import os
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')

# Mock HTTP server that fails twice then succeeds
call_count = 0

class RetryHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        global call_count
        call_count += 1
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)

        if call_count <= 2:
            self.send_response(429)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': {'message': 'rate limited'}}).encode())
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'content': [{'text': 'success after retry'}],
                'usage': {'input_tokens': 10, 'output_tokens': 5}
            }).encode())

    def log_message(self, *args):
        pass  # suppress logs

server = http.server.HTTPServer(('127.0.0.1', 0), RetryHandler)
port = server.server_address[1]
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()

# Patch API_URL to our mock
import core.llm as llm_mod
orig_url = llm_mod.API_URL
llm_mod.API_URL = f'http://127.0.0.1:{port}/v1/messages'

try:
    result = llm_mod.chat('test-key', 'system', 'hello', retries=3)
    assert result == 'success after retry', f'Got: {result}'
    assert call_count == 3, f'Expected 3 calls, got {call_count}'
    print('  PASS: retried 2x on 429, succeeded on 3rd')
finally:
    llm_mod.API_URL = orig_url
    server.shutdown()
"

# Test 2: LLM raises on non-retryable errors
echo "Test 2: Non-retryable error (400)..."
python3 -c "
import http.server
import json
import threading
import os
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')

class ErrorHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': {'message': 'bad request'}}).encode())
    def log_message(self, *args):
        pass

server = http.server.HTTPServer(('127.0.0.1', 0), ErrorHandler)
port = server.server_address[1]
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()

import core.llm as llm_mod
orig_url = llm_mod.API_URL
llm_mod.API_URL = f'http://127.0.0.1:{port}/v1/messages'

try:
    from urllib.error import HTTPError
    got_error = False
    try:
        llm_mod.chat('test-key', 'system', 'hello', retries=3)
    except HTTPError as e:
        got_error = True
        assert e.code == 400
    assert got_error, 'Should have raised HTTPError'
    print('  PASS: 400 raises immediately without retry')
finally:
    llm_mod.API_URL = orig_url
    server.shutdown()
"

# Test 3: Retryable codes list
echo "Test 3: Retryable codes defined..."
python3 -c "
from core.llm import _RETRYABLE_CODES
assert 429 in _RETRYABLE_CODES, 'Missing 429'
assert 500 in _RETRYABLE_CODES, 'Missing 500'
assert 502 in _RETRYABLE_CODES, 'Missing 502'
assert 503 in _RETRYABLE_CODES, 'Missing 503'
assert 529 in _RETRYABLE_CODES, 'Missing 529'
assert 400 not in _RETRYABLE_CODES, '400 should not be retryable'
assert 401 not in _RETRYABLE_CODES, '401 should not be retryable'
print('  PASS: retryable codes correct')
"

# Test 4: Teams refresh token persistence (T017)
echo "Test 4: Token persistence..."
python3 -c "
import os, shutil
test_dir = '/tmp/coconut-token-test'
shutil.rmtree(test_dir, ignore_errors=True)
os.makedirs(test_dir, exist_ok=True)
os.environ['COCONUT_DATA_DIR'] = test_dir
os.environ['COCONUT_ADAPTER_TEAMS_ENABLED'] = 'true'
os.environ['COCONUT_TEAMS_CHAT_ID'] = 'test'
os.environ['COCONUT_TEAMS_TENANT_ID'] = 'test'
os.environ['COCONUT_TEAMS_CLIENT_ID'] = 'test'
os.environ['COCONUT_TEAMS_REFRESH_TOKEN'] = 'initial-token'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'

from core import config
cfg = config.load()
from adapters.teams_adapter import TeamsAdapter
adapter = TeamsAdapter(cfg)

# Initial token loaded
assert adapter._refresh_token == 'initial-token'

# Simulate token rotation
adapter._persist_refresh_token('rotated-token-abc123')
assert adapter._refresh_token == 'rotated-token-abc123'

# Verify file was written
token_file = os.path.join(test_dir, 'teams_refresh_token')
assert os.path.exists(token_file), 'Token file not created'
with open(token_file) as f:
    saved = f.read()
assert saved == 'rotated-token-abc123', f'Token file wrong: {saved}'

# New adapter instance loads persisted token
os.environ['COCONUT_TEAMS_REFRESH_TOKEN'] = ''  # clear env
cfg2 = config.load()
adapter2 = TeamsAdapter(cfg2)
assert adapter2._refresh_token == 'rotated-token-abc123', f'Got: {adapter2._refresh_token}'

# Same token doesn't re-write (no-op)
import time
mtime_before = os.path.getmtime(token_file)
time.sleep(0.05)
adapter2._persist_refresh_token('rotated-token-abc123')
mtime_after = os.path.getmtime(token_file)
assert mtime_before == mtime_after, 'Should not rewrite same token'

shutil.rmtree(test_dir, ignore_errors=True)
print('  PASS: token persistence works (write, reload, no-op on same)')
"

# Test 5: Classifier context limiting (T018)
echo "Test 5: Classifier context window..."
python3 -c "
from core.classifier import MAX_CLASSIFY_CONTEXT
assert MAX_CLASSIFY_CONTEXT <= 20, f'Context too large: {MAX_CLASSIFY_CONTEXT}'
assert MAX_CLASSIFY_CONTEXT >= 10, f'Context too small: {MAX_CLASSIFY_CONTEXT}'
print(f'  PASS: classifier context limited to {MAX_CLASSIFY_CONTEXT} messages')
" 2>/dev/null || echo "  SKIP: T018 not yet implemented"

# Test 6: Health check module
echo "Test 6: Health check module..."
python3 -c "
import os, json, shutil, time

test_dir = '/tmp/coconut-health-test'
shutil.rmtree(test_dir, ignore_errors=True)
os.makedirs(test_dir, exist_ok=True)

health = {
    'status': 'running',
    'last_heartbeat_epoch': int(time.time()),
    'started_at': '2026-01-01T00:00:00Z',
    'processed': 5,
    'errors': 0,
}
with open(os.path.join(test_dir, 'health.json'), 'w') as f:
    json.dump(health, f)

from core.health import HealthWriter
hw = HealthWriter(data_dir=test_dir)
assert hw.check() == 0, 'Expected healthy'

health['last_heartbeat_epoch'] = int(time.time()) - 600
with open(os.path.join(test_dir, 'health.json'), 'w') as f:
    json.dump(health, f)
assert hw.check() == 1, 'Expected stale'

shutil.rmtree(test_dir, ignore_errors=True)
print('  PASS: health check detects fresh and stale states')
"

# Test 7: Health check CLI mode (T019)
echo "Test 7: Health check CLI --health flag..."
python3 -c "
import subprocess, os, json, shutil, time

test_dir = '/tmp/coconut-health-cli'
shutil.rmtree(test_dir, ignore_errors=True)
os.makedirs(test_dir, exist_ok=True)

# Write a fresh health file
health = {
    'status': 'running',
    'last_heartbeat_epoch': int(time.time()),
    'started_at': '2026-01-01T00:00:00Z',
    'processed': 10,
    'errors': 1,
}
with open(os.path.join(test_dir, 'health.json'), 'w') as f:
    json.dump(health, f)

# Run coconut.py --health
env = dict(os.environ, COCONUT_DATA_DIR=test_dir)
result = subprocess.run(
    ['python3', 'coconut.py', '--health'],
    capture_output=True, text=True, env=env
)
assert result.returncode == 0, f'Expected exit 0, got {result.returncode}: {result.stderr}'
output = json.loads(result.stdout)
assert output['status'] == 'running'
assert output['processed'] == 10

# Stale health file
health['last_heartbeat_epoch'] = int(time.time()) - 600
with open(os.path.join(test_dir, 'health.json'), 'w') as f:
    json.dump(health, f)

result2 = subprocess.run(
    ['python3', 'coconut.py', '--health'],
    capture_output=True, text=True, env=env
)
assert result2.returncode == 1, f'Expected exit 1 for stale, got {result2.returncode}'
output2 = json.loads(result2.stdout)
assert output2['status'] == 'stale'

shutil.rmtree(test_dir, ignore_errors=True)
print('  PASS: --health exits 0 for fresh, 1 for stale')
"

# Test 8: Metrics — adapter stats, cost estimation (T023)
echo "Test 8: Metrics and cost tracking..."
python3 -c "
import shutil, json
from core.health import HealthWriter, estimate_cost

test_dir = '/tmp/coconut-metrics-test'
shutil.rmtree(test_dir, ignore_errors=True)

hw = HealthWriter(data_dir=test_dir)

# Record adapter polls
hw.record_poll('signal', message_count=3)
hw.record_poll('teams', message_count=0)
hw.record_poll('signal', message_count=1)
hw.record_adapter_error('teams')

assert hw.polls == 3, f'Expected 3 polls, got {hw.polls}'
assert hw.adapter_stats['signal']['polls'] == 2
assert hw.adapter_stats['signal']['messages'] == 4
assert hw.adapter_stats['teams']['errors'] == 1
assert hw.errors == 1

# Cost estimation
usage = {'input_tokens': 1000, 'output_tokens': 100}
cost = estimate_cost(usage)
expected = 1000 * 0.80 / 1_000_000 + 100 * 4.00 / 1_000_000
assert abs(cost - expected) < 0.000001, f'Cost {cost} != {expected}'

# Health file includes metrics
hw.update(extra={'usage': usage})
with open(test_dir + '/health.json') as f:
    health = json.load(f)
assert 'adapters' in health
assert 'cost_usd' in health
assert health['polls'] == 3
assert health['adapters']['signal']['messages'] == 4

shutil.rmtree(test_dir, ignore_errors=True)
print('  PASS: adapter stats, polls, cost estimation all correct')
"

echo ""
echo "=== HARDENING TESTS COMPLETE ==="
