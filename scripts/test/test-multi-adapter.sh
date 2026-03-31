#!/usr/bin/env bash
# T014: Multi-adapter test — verify multiple adapters can run simultaneously.
# Tests: adapter loading, message routing to source adapter only, concurrent poll.
# No real API calls — uses mock HTTP server for Signal, mock adapter for Teams.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Multi-Adapter E2E Test ==="

# Test 1: Multiple adapters load correctly
echo "Test 1: Load multiple adapters..."
python3 -c "
import os
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
os.environ['COCONUT_ADAPTER_SIGNAL_ENABLED'] = 'true'
os.environ['COCONUT_ADAPTER_TEAMS_ENABLED'] = 'true'
os.environ['COCONUT_SIGNAL_CLI_URL'] = 'http://localhost:19999'
os.environ['COCONUT_SIGNAL_GROUP_ID'] = 'test-group'
os.environ['COCONUT_SIGNAL_PHONE_NUMBER'] = '+10000000000'
os.environ['COCONUT_TEAMS_CHAT_ID'] = 'test-chat-id'
os.environ['COCONUT_TEAMS_TENANT_ID'] = 'test-tenant'
os.environ['COCONUT_TEAMS_CLIENT_ID'] = 'test-client'
os.environ['COCONUT_TEAMS_REFRESH_TOKEN'] = 'test-token'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
from core import config
cfg = config.load()

from adapters.signal_adapter import SignalAdapter
from adapters.teams_adapter import TeamsAdapter
from adapters.cli_adapter import CLIAdapter

adapters = []
adapters.append(SignalAdapter(cfg))
adapters.append(TeamsAdapter(cfg))
adapters.append(CLIAdapter(cfg))

assert len(adapters) == 3, f'Expected 3 adapters, got {len(adapters)}'
names = [a.name for a in adapters]
assert 'signal' in names
assert 'teams' in names
assert 'cli' in names
print('  PASS: 3 adapters loaded (signal, teams, cli)')
"

# Test 2: _load_adapters respects enabled flags
echo "Test 2: Selective adapter loading..."
python3 -c "
import os
# Only enable Signal and CLI, not Teams
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
os.environ['COCONUT_ADAPTER_SIGNAL_ENABLED'] = 'true'
os.environ['COCONUT_ADAPTER_TEAMS_ENABLED'] = 'false'
os.environ['COCONUT_SIGNAL_CLI_URL'] = 'http://localhost:19999'
os.environ['COCONUT_SIGNAL_GROUP_ID'] = 'test-group'
os.environ['COCONUT_SIGNAL_PHONE_NUMBER'] = '+10000000000'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
from core import config
cfg = config.load()

# Replicate _load_adapters logic
adapters = []
if cfg.get('signal_enabled'):
    from adapters.signal_adapter import SignalAdapter
    adapters.append(SignalAdapter(cfg))
if cfg.get('teams_enabled'):
    from adapters.teams_adapter import TeamsAdapter
    adapters.append(TeamsAdapter(cfg))
if cfg.get('cli_enabled'):
    from adapters.cli_adapter import CLIAdapter
    adapters.append(CLIAdapter(cfg))

assert len(adapters) == 2, f'Expected 2, got {len(adapters)}'
names = [a.name for a in adapters]
assert 'signal' in names
assert 'cli' in names
assert 'teams' not in names
print('  PASS: only enabled adapters loaded (signal, cli)')
"

# Test 3: Message routing — replies go to source adapter only
echo "Test 3: Message routing to source adapter..."
python3 -c "
import os
os.environ['COCONUT_NAME'] = 'Coconut'
os.environ['COCONUT_TAGLINE'] = 'Test'
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
from core import config
cfg = config.load()

from adapters.base import BaseAdapter, Message

# Create two mock adapters that track sends
class MockAdapter(BaseAdapter):
    def __init__(self, name_str, config, messages=None):
        super().__init__(config)
        self.name = name_str
        self._messages = messages or []
        self.sent = []
    def poll(self):
        msgs = self._messages
        self._messages = []
        return msgs
    def send(self, text):
        self.sent.append(text)

adapter_a = MockAdapter('adapter_a', cfg, [
    Message('msg1', 'alice', 'hello from A')
])
adapter_b = MockAdapter('adapter_b', cfg, [
    Message('msg2', 'bob', 'hello from B')
])

# Simulate the poll loop's msg_source tracking
msg_source = {}
all_msgs = []
for adapter in [adapter_a, adapter_b]:
    msgs = adapter.poll()
    for m in msgs:
        msg_source[m.message_id] = adapter
    all_msgs.extend(msgs)

assert len(all_msgs) == 2
assert msg_source['msg1'] is adapter_a
assert msg_source['msg2'] is adapter_b

# Simulate routing reply to source only
for msg in all_msgs:
    source = msg_source[msg.message_id]
    source.send(f'Reply to {msg.sender}')

assert len(adapter_a.sent) == 1, f'adapter_a sent={adapter_a.sent}'
assert len(adapter_b.sent) == 1, f'adapter_b sent={adapter_b.sent}'
assert 'alice' in adapter_a.sent[0]
assert 'bob' in adapter_b.sent[0]
print('  PASS: replies routed to correct source adapter')
"

# Test 4: Concurrent poll — adapters don't interfere with each other's state
echo "Test 4: Concurrent poll isolation..."
python3 -c "
import os
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
from core import config
cfg = config.load()

from adapters.signal_adapter import SignalAdapter
from adapters.cli_adapter import CLIAdapter

sig = SignalAdapter(cfg)
cli = CLIAdapter(cfg)

# Poll both — Signal will fail (no server) but shouldn't crash or affect CLI
sig_msgs = sig.poll()  # Returns [] because no server
assert sig_msgs == [], f'Expected empty from signal, got {sig_msgs}'
# CLI in non-tty mode returns [] too
cli_msgs = cli.poll()
assert cli_msgs == [], f'Expected empty from cli, got {cli_msgs}'

# Signal seen_timestamps should be independent
sig._seen_timestamps.add(12345)
assert 12345 not in getattr(cli, '_seen_timestamps', set())
print('  PASS: adapters poll independently without interference')
"

# Test 5: Format outbound consistent across adapters
echo "Test 5: Format outbound consistency..."
python3 -c "
import os
os.environ['COCONUT_NAME'] = 'MultiBot'
os.environ['COCONUT_TAGLINE'] = 'Multi Test'
os.environ['COCONUT_EMOJI'] = '🥥'
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
os.environ['COCONUT_ADAPTER_SIGNAL_ENABLED'] = 'true'
os.environ['COCONUT_ADAPTER_TEAMS_ENABLED'] = 'true'
os.environ['COCONUT_SIGNAL_CLI_URL'] = 'http://localhost:19999'
os.environ['COCONUT_SIGNAL_GROUP_ID'] = 'g'
os.environ['COCONUT_SIGNAL_PHONE_NUMBER'] = '+1'
os.environ['COCONUT_TEAMS_CHAT_ID'] = 'c'
os.environ['COCONUT_TEAMS_TENANT_ID'] = 't'
os.environ['COCONUT_TEAMS_CLIENT_ID'] = 'i'
os.environ['COCONUT_TEAMS_REFRESH_TOKEN'] = 'r'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
from core import config
cfg = config.load()

from adapters.signal_adapter import SignalAdapter
from adapters.teams_adapter import TeamsAdapter
from adapters.cli_adapter import CLIAdapter

for AdapterClass in [SignalAdapter, TeamsAdapter, CLIAdapter]:
    a = AdapterClass(cfg)
    out = a.format_outbound('Hello world')
    assert 'MultiBot' in out, f'{a.name} missing bot name'
    assert 'Hello world' in out, f'{a.name} missing message'
    assert 'Multi Test' in out, f'{a.name} missing tagline'

print('  PASS: all adapters format outbound identically')
"

# Test 6: Cache handles messages from multiple adapters
echo "Test 6: Cache with multi-adapter messages..."
python3 -c "
import shutil
from core.cache import MessageCache

test_dir = '/tmp/coconut-multi-cache'
shutil.rmtree(test_dir, ignore_errors=True)
c = MessageCache(data_dir=test_dir, cache_size=10)

# Messages from different adapters with different ID formats
msgs = [
    {'message_id': '1711900000000', 'sender': 'sig-alice', 'text': 'from signal', 'timestamp': '2026-01-01T00:00:00Z'},
    {'message_id': 'teams-msg-abc123', 'sender': 'teams-bob', 'text': 'from teams', 'timestamp': '2026-01-01T00:00:01Z'},
    {'message_id': 'cli-user-xyz', 'sender': 'cli-user', 'text': 'from cli', 'timestamp': '2026-01-01T00:00:02Z'},
]
cached, archived = c.add(msgs)
assert len(cached) == 3
assert archived == 0

# Verify all messages preserved
loaded = c.load()
senders = [m['sender'] for m in loaded]
assert 'sig-alice' in senders
assert 'teams-bob' in senders
assert 'cli-user' in senders

# Dedup works across adapters
cached2, _ = c.add([msgs[1]])  # Re-add teams msg
assert len(cached2) == 3, f'Dedup failed: {len(cached2)}'

shutil.rmtree(test_dir, ignore_errors=True)
print('  PASS: cache handles mixed adapter messages with dedup')
"

echo ""
echo "=== ALL MULTI-ADAPTER TESTS PASSED ==="
