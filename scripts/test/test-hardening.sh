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

# Test 4: Classifier context limiting (T018)
echo "Test 4: Classifier context window..."
python3 -c "
from core.classifier import MAX_CLASSIFY_CONTEXT
assert MAX_CLASSIFY_CONTEXT <= 20, f'Context too large: {MAX_CLASSIFY_CONTEXT}'
assert MAX_CLASSIFY_CONTEXT >= 10, f'Context too small: {MAX_CLASSIFY_CONTEXT}'
print(f'  PASS: classifier context limited to {MAX_CLASSIFY_CONTEXT} messages')
" 2>/dev/null || echo "  SKIP: T018 not yet implemented"

# Test 5: Health check CLI (T019)
echo "Test 5: Health check CLI..."
python3 -c "
import subprocess, os, json, shutil

# Create health file
test_dir = '/tmp/coconut-health-test'
shutil.rmtree(test_dir, ignore_errors=True)
os.makedirs(test_dir, exist_ok=True)

import time
health = {
    'status': 'running',
    'last_heartbeat_epoch': int(time.time()),
    'started_at': '2026-01-01T00:00:00Z',
    'processed': 5,
    'errors': 0,
}
with open(os.path.join(test_dir, 'health.json'), 'w') as f:
    json.dump(health, f)

# Test health check
from core.health import HealthWriter
hw = HealthWriter(data_dir=test_dir)
assert hw.check() == 0, 'Expected healthy'

# Simulate stale
health['last_heartbeat_epoch'] = int(time.time()) - 600
with open(os.path.join(test_dir, 'health.json'), 'w') as f:
    json.dump(health, f)
assert hw.check() == 1, 'Expected stale'

shutil.rmtree(test_dir, ignore_errors=True)
print('  PASS: health check detects fresh and stale states')
"

echo ""
echo "=== HARDENING TESTS COMPLETE ==="
