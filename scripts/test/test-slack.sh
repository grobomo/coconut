#!/usr/bin/env bash
# T039: Slack adapter tests — mock API, no real Slack connection needed
set -euo pipefail
cd "$(dirname "$0")/../.."

PASS=0; FAIL=0
pass() { PASS=$((PASS+1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }

echo "=== Slack Adapter Tests ==="

# Test 1: Import
echo "Test 1: Slack adapter imports..."
python3 -c "
from adapters.slack_adapter import SlackAdapter
print('OK')
" && pass "slack adapter imports" || fail "slack adapter imports"

# Test 2: Config loading includes Slack fields
echo "Test 2: Config includes slack fields..."
python3 -c "
import os
os.environ['COCONUT_ADAPTER_SLACK_ENABLED'] = 'true'
os.environ['COCONUT_SLACK_BOT_TOKEN'] = 'xoxb-test-token'
os.environ['COCONUT_SLACK_CHANNEL_ID'] = 'C1234567890'
from core.config import load
cfg = load()
assert cfg['slack_enabled'] is True
assert cfg['slack_bot_token'] == 'xoxb-test-token'
assert cfg['slack_channel_id'] == 'C1234567890'
print('OK')
" && pass "slack config loaded" || fail "slack config loaded"

# Test 3: Adapter initialization
echo "Test 3: Adapter initialization..."
python3 -c "
from adapters.slack_adapter import SlackAdapter

cfg = {
    'slack_bot_token': 'xoxb-test',
    'slack_channel_id': 'C123',
    'name': 'TestBot',
    'tagline': 'Test',
}
adapter = SlackAdapter(cfg)
assert adapter.name == 'slack'
assert adapter.bot_token == 'xoxb-test'
assert adapter.channel_id == 'C123'
assert adapter._seen_ts == set()
print('OK')
" && pass "adapter initializes" || fail "adapter initializes"

# Test 4: Timestamp conversion
echo "Test 4: Timestamp conversion..."
python3 -c "
from adapters.slack_adapter import SlackAdapter

# Slack ts format: epoch.sequence
assert SlackAdapter._ts_to_iso('1711900000.000100') == '2024-03-31T15:46:40Z'
assert SlackAdapter._ts_to_iso('invalid') == ''
assert SlackAdapter._ts_to_iso('') == ''
print('OK')
" && pass "timestamp conversion" || fail "timestamp conversion"

# Test 5: Mock API polling with fake HTTP server
echo "Test 5: Mock API polling..."
python3 -c "
import json, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from adapters.slack_adapter import SlackAdapter

# Mock Slack API server
class MockSlack(BaseHTTPRequestHandler):
    def do_GET(self):
        if 'conversations.history' in self.path:
            # Slack returns newest first
            resp = {
                'ok': True,
                'messages': [
                    {'ts': '9999999999.000003', 'subtype': 'channel_join', 'user': 'U333', 'text': 'joined'},
                    {'ts': '9999999999.000002', 'user': 'U222', 'text': 'How are you?'},
                    {'ts': '9999999999.000001', 'user': 'U111', 'text': 'Hello coconut'},
                ]
            }
        elif 'users.info' in self.path:
            resp = {
                'ok': True,
                'user': {'profile': {'display_name': 'TestUser', 'real_name': 'Test User'}}
            }
        elif 'auth.test' in self.path:
            resp = {'ok': True, 'user_id': 'UBOT'}
        else:
            resp = {'ok': False, 'error': 'unknown_method'}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())
    def log_message(self, fmt, *args):
        pass

server = HTTPServer(('127.0.0.1', 18997), MockSlack)
threading.Thread(target=server.serve_forever, daemon=True).start()
time.sleep(0.2)

# Patch SLACK_API to use our mock
import adapters.slack_adapter as sa
sa.SLACK_API = 'http://127.0.0.1:18997'

cfg = {
    'slack_bot_token': 'xoxb-test',
    'slack_channel_id': 'C123',
    'name': 'Coconut',
}
adapter = SlackAdapter(cfg)
adapter._last_ts = '0'  # Get all messages

msgs = adapter.poll()
# Should get 2 messages (channel_join subtype filtered out)
assert len(msgs) == 2, f'Expected 2, got {len(msgs)}: {[m.text for m in msgs]}'
assert msgs[0].text == 'Hello coconut'
assert msgs[1].text == 'How are you?'
assert msgs[0].sender == 'TestUser'

# Second poll should return nothing (dedup)
msgs2 = adapter.poll()
assert len(msgs2) == 0, f'Expected 0 on second poll, got {len(msgs2)}'

server.shutdown()
print('OK')
" && pass "mock API polling works" || fail "mock API polling works"

# Test 6: Send via mock API
echo "Test 6: Mock API send..."
python3 -c "
import json, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from adapters.slack_adapter import SlackAdapter

received = []

class MockSlack(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        received.append(body)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'ts': '123.456'}).encode())
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'user_id': 'UBOT'}).encode())
    def log_message(self, fmt, *args):
        pass

server = HTTPServer(('127.0.0.1', 18998), MockSlack)
threading.Thread(target=server.serve_forever, daemon=True).start()
time.sleep(0.2)

import adapters.slack_adapter as sa
sa.SLACK_API = 'http://127.0.0.1:18998'

cfg = {
    'slack_bot_token': 'xoxb-test',
    'slack_channel_id': 'C123',
    'name': 'Coconut',
    'tagline': 'AI Advisor',
    'emoji': '🌴',
}
adapter = SlackAdapter(cfg)
adapter.send('Hello from coconut!')

assert len(received) == 1, f'Expected 1 send, got {len(received)}'
assert received[0]['channel'] == 'C123'
assert 'Hello from coconut!' in received[0]['text']
assert 'Coconut' in received[0]['text']

server.shutdown()
print('OK')
" && pass "send via mock API" || fail "send via mock API"

# Test 7: Bot self-message filtering
echo "Test 7: Bot self-message filtering..."
python3 -c "
import json, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from adapters.slack_adapter import SlackAdapter

class MockSlack(BaseHTTPRequestHandler):
    def do_GET(self):
        if 'conversations.history' in self.path:
            resp = {
                'ok': True,
                'messages': [
                    {'ts': '8888888888.000001', 'user': 'UBOT', 'text': 'I am the bot'},
                    {'ts': '8888888888.000002', 'user': 'U111', 'text': 'Real user msg'},
                ]
            }
        elif 'auth.test' in self.path:
            resp = {'ok': True, 'user_id': 'UBOT'}
        elif 'users.info' in self.path:
            resp = {'ok': True, 'user': {'profile': {'display_name': 'Human'}}}
        else:
            resp = {'ok': False}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())
    def log_message(self, fmt, *args):
        pass

server = HTTPServer(('127.0.0.1', 18999), MockSlack)
threading.Thread(target=server.serve_forever, daemon=True).start()
time.sleep(0.2)

import adapters.slack_adapter as sa
sa.SLACK_API = 'http://127.0.0.1:18999'

cfg = {'slack_bot_token': 'xoxb-test', 'slack_channel_id': 'C123', 'name': 'Bot'}
adapter = SlackAdapter(cfg)
adapter._last_ts = '0'

msgs = adapter.poll()
assert len(msgs) == 1, f'Expected 1 (bot msg filtered), got {len(msgs)}'
assert msgs[0].text == 'Real user msg'

server.shutdown()
print('OK')
" && pass "bot self-messages filtered" || fail "bot self-messages filtered"

# Test 8: Coconut.py loads slack adapter
echo "Test 8: Integration — coconut.py loads slack..."
python3 -c "
import ast
with open('coconut.py') as f:
    tree = ast.parse(f.read())
# Check that 'slack_enabled' appears in the source
with open('coconut.py') as f:
    src = f.read()
assert 'slack_enabled' in src, 'coconut.py must check slack_enabled'
assert 'SlackAdapter' in src, 'coconut.py must import SlackAdapter'
print('OK')
" && pass "coconut.py loads slack adapter" || fail "coconut.py loads slack adapter"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
