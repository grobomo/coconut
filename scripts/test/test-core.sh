#!/usr/bin/env bash
# T002/T003: Verify core modules and adapters import cleanly.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

echo "Testing imports..."
python3 -c "
from core import config, llm, classifier, cache
from adapters.base import BaseAdapter, Message
from adapters.cli_adapter import CLIAdapter
from adapters.signal_adapter import SignalAdapter
from adapters.teams_adapter import TeamsAdapter

# Test config loader
import os
os.environ['COCONUT_NAME'] = 'TestBot'
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
cfg = config.load()
assert cfg['name'] == 'TestBot', f'Expected TestBot, got {cfg[\"name\"]}'
assert cfg['cli_enabled'] is True
assert cfg['poll_interval'] == 3

# Test cache
c = cache.MessageCache(data_dir='/tmp/coconut-test', cache_size=5)
msgs = [{'message_id': str(i), 'sender': 'test', 'text': f'msg {i}', 'timestamp': '2026-01-01'} for i in range(8)]
cached, archived = c.add(msgs)
assert len(cached) == 5, f'Expected 5 cached, got {len(cached)}'
assert archived == 3, f'Expected 3 archived, got {archived}'

# Test Message
m = Message('id1', 'alice', 'hello')
d = m.to_dict()
assert d['sender'] == 'alice'
assert d['text'] == 'hello'

# Test system prompt building
os.environ['COCONUT_SYSTEM_PROMPT_FILE'] = '/nonexistent'
cfg2 = config.load()
prompt = llm.build_system_prompt(cfg2)
assert 'TestBot' in prompt

print('ALL CORE TESTS PASSED')
"

# Clean up test data
rm -rf /tmp/coconut-test

echo "CORE TEST PASSED"
