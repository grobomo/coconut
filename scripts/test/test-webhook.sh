#!/usr/bin/env bash
# Test webhook adapter — HTTP server, inbound messages, HMAC auth, health endpoint
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "=== Webhook Adapter Tests ==="

# Test 1: Module imports
echo "Test 1: Webhook adapter imports..."
python3 -c "
from adapters.webhook_adapter import WebhookAdapter
from adapters.base import Message
print('  PASS: webhook adapter imports')
"

# Test 2: HTTP server starts and health endpoint works
echo "Test 2: HTTP server and health endpoint..."
python3 -c "
import json, time, urllib.request
from adapters.webhook_adapter import WebhookAdapter

cfg = {'webhook_port': 18990, 'webhook_path': '/webhook/inbound'}
adapter = WebhookAdapter(cfg)
time.sleep(0.2)

# Health endpoint
resp = urllib.request.urlopen('http://127.0.0.1:18990/webhook/health', timeout=5)
data = json.loads(resp.read())
assert data['status'] == 'ok', f'health status: {data}'
assert data['queue_size'] == 0

adapter.shutdown()
print('  PASS: HTTP server starts, health endpoint responds')
"

# Test 3: Inbound message via POST
echo "Test 3: Inbound POST message..."
python3 -c "
import json, time, urllib.request
from adapters.webhook_adapter import WebhookAdapter

cfg = {'webhook_port': 18991, 'webhook_path': '/webhook/inbound'}
adapter = WebhookAdapter(cfg)
time.sleep(0.2)

# POST a message
payload = json.dumps({'text': 'Hello from webhook', 'sender': 'test-user'}).encode()
req = urllib.request.Request('http://127.0.0.1:18991/webhook/inbound', data=payload, method='POST')
req.add_header('Content-Type', 'application/json')
resp = urllib.request.urlopen(req, timeout=5)
result = json.loads(resp.read())
assert result['status'] == 'accepted', f'unexpected: {result}'
assert resp.status == 202

# Poll should return the message
msgs = adapter.poll()
assert len(msgs) == 1, f'expected 1 message, got {len(msgs)}'
assert msgs[0].text == 'Hello from webhook'
assert msgs[0].sender == 'test-user'

# Second poll should be empty
msgs2 = adapter.poll()
assert len(msgs2) == 0, 'queue should be drained'

adapter.shutdown()
print('  PASS: inbound POST accepted and polled')
"

# Test 4: HMAC signature verification
echo "Test 4: HMAC signature verification..."
python3 -c "
import json, hashlib, hmac, time, urllib.request, urllib.error
from adapters.webhook_adapter import WebhookAdapter

secret = 'test-secret-key-123'
cfg = {'webhook_port': 18992, 'webhook_path': '/webhook/inbound', 'webhook_secret': secret}
adapter = WebhookAdapter(cfg)
time.sleep(0.2)

payload = json.dumps({'text': 'Signed message', 'sender': 'auth-user'}).encode()

# Without signature — should get 403
req = urllib.request.Request('http://127.0.0.1:18992/webhook/inbound', data=payload, method='POST')
req.add_header('Content-Type', 'application/json')
try:
    urllib.request.urlopen(req, timeout=5)
    assert False, 'should have gotten 403'
except urllib.error.HTTPError as e:
    assert e.code == 403, f'expected 403, got {e.code}'

# With valid signature — should get 202
sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
req2 = urllib.request.Request('http://127.0.0.1:18992/webhook/inbound', data=payload, method='POST')
req2.add_header('Content-Type', 'application/json')
req2.add_header('X-Webhook-Signature', sig)
resp = urllib.request.urlopen(req2, timeout=5)
assert resp.status == 202

msgs = adapter.poll()
assert len(msgs) == 1 and msgs[0].text == 'Signed message'

adapter.shutdown()
print('  PASS: HMAC auth rejects unsigned, accepts signed')
"

# Test 5: Invalid requests (empty body, bad JSON, missing text)
echo "Test 5: Invalid request handling..."
python3 -c "
import json, urllib.request, urllib.error, time
from adapters.webhook_adapter import WebhookAdapter

cfg = {'webhook_port': 18993, 'webhook_path': '/webhook/inbound'}
adapter = WebhookAdapter(cfg)
time.sleep(0.2)

def post(data, expect_code):
    body = data.encode() if isinstance(data, str) else data
    req = urllib.request.Request('http://127.0.0.1:18993/webhook/inbound', data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.status == expect_code, f'expected {expect_code}, got {resp.status}'
    except urllib.error.HTTPError as e:
        assert e.code == expect_code, f'expected {expect_code}, got {e.code}'

# Bad JSON
post('not-json', 400)
# Missing text
post(json.dumps({'sender': 'nobody'}), 400)
# Wrong path
try:
    req = urllib.request.Request('http://127.0.0.1:18993/wrong/path', data=b'{}', method='POST')
    urllib.request.urlopen(req, timeout=5)
    assert False
except urllib.error.HTTPError as e:
    assert e.code == 404

# Valid
post(json.dumps({'text': 'ok'}), 202)

adapter.shutdown()
print('  PASS: invalid requests rejected correctly')
"

# Test 6: Callback URL send
echo "Test 6: Outbound callback send..."
python3 -c "
import json, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from adapters.webhook_adapter import WebhookAdapter

received = []

class CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        received.append(body)
        self.send_response(200)
        self.end_headers()
    def log_message(self, fmt, *args):
        pass

cb_server = HTTPServer(('127.0.0.1', 18994), CallbackHandler)
cb_thread = threading.Thread(target=cb_server.serve_forever, daemon=True)
cb_thread.start()

cfg = {
    'webhook_port': 18995,
    'webhook_path': '/webhook/inbound',
    'webhook_callback_url': 'http://127.0.0.1:18994/callback',
    'name': 'TestBot',
}
adapter = WebhookAdapter(cfg)
time.sleep(0.2)

# Post inbound message (sets last_callback)
import urllib.request
payload = json.dumps({'text': 'trigger reply', 'sender': 'user1', 'callback_url': 'http://127.0.0.1:18994/callback'}).encode()
req = urllib.request.Request('http://127.0.0.1:18995/webhook/inbound', data=payload, method='POST')
req.add_header('Content-Type', 'application/json')
urllib.request.urlopen(req, timeout=5)
adapter.poll()

# Send reply
adapter.send('Here is my reply')
time.sleep(0.3)

assert len(received) == 1, f'expected 1 callback, got {len(received)}'
assert 'Here is my reply' in received[0]['text']

adapter.shutdown()
cb_server.shutdown()
print('  PASS: outbound reply delivered to callback URL')
"

# Test 7: Body size limit (413 for oversized payloads)
echo "Test 7: Body size limit..."
python3 -c "
import urllib.request, urllib.error, time
from adapters.webhook_adapter import WebhookAdapter, MAX_BODY_SIZE

cfg = {'webhook_port': 18996, 'webhook_path': '/webhook/inbound'}
adapter = WebhookAdapter(cfg)
time.sleep(0.2)

# Oversized payload — should get 413 (or ConnectionAbortedError on Windows
# when server closes socket while client is still sending large body)
big_body = b'x' * (MAX_BODY_SIZE + 1)
req = urllib.request.Request('http://127.0.0.1:18996/webhook/inbound', data=big_body, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('Content-Length', str(len(big_body)))
try:
    urllib.request.urlopen(req, timeout=5)
    assert False, 'should have gotten 413'
except urllib.error.HTTPError as e:
    assert e.code == 413, f'expected 413, got {e.code}'
except (ConnectionAbortedError, ConnectionResetError, urllib.error.URLError):
    pass  # Windows: server closes connection while client sends large body

adapter.shutdown()
print('  PASS: oversized payload rejected with 413')
"

# Test 8: Config loading includes webhook fields
echo "Test 8: Config includes webhook fields..."
python3 -c "
import os
os.environ['COCONUT_ADAPTER_WEBHOOK_ENABLED'] = 'true'
os.environ['COCONUT_WEBHOOK_PORT'] = '9999'
os.environ['COCONUT_WEBHOOK_SECRET'] = 'mysecret'
from core.config import load
cfg = load()
assert cfg['webhook_enabled'] is True
assert cfg['webhook_port'] == 9999
assert cfg['webhook_secret'] == 'mysecret'
print('  PASS: webhook config loaded from env vars')
"

echo ""
echo "=== WEBHOOK TESTS COMPLETE ==="
