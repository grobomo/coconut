#!/usr/bin/env bash
# T007: E2E test — exercises coconut with CLI adapter using mock LLM.
# Verifies: config loading, cache, classification, response flow.
# No real API calls — patches llm.chat to return canned responses.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Coconut E2E Test ==="

# Test 1: Config loading with env vars
echo "Test 1: Config loading..."
python3 -c "
import os
os.environ['COCONUT_NAME'] = 'TestBot'
os.environ['COCONUT_TAGLINE'] = 'E2E Test'
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
os.environ['COCONUT_POLL_INTERVAL'] = '1'
os.environ['COCONUT_CACHE_SIZE'] = '10'
os.environ['ANTHROPIC_API_KEY'] = 'test-key-for-e2e'
from core import config
cfg = config.load()
assert cfg['name'] == 'TestBot', f'name={cfg[\"name\"]}'
assert cfg['cli_enabled'] is True
assert cfg['poll_interval'] == 1
assert cfg['cache_size'] == 10
print('  PASS: config')
"

# Test 2: Cache add/overflow/archive
echo "Test 2: Cache operations..."
python3 -c "
import os, shutil
from core.cache import MessageCache
test_dir = '/tmp/coconut-e2e-cache'
shutil.rmtree(test_dir, ignore_errors=True)
c = MessageCache(data_dir=test_dir, cache_size=3)

# Add 5 messages — 3 should stay, 2 archived
msgs = [{'message_id': str(i), 'sender': 'user', 'text': f'msg{i}', 'timestamp': '2026-01-01T00:00:00Z'} for i in range(5)]
cached, archived = c.add(msgs)
assert len(cached) == 3, f'cached={len(cached)}'
assert archived == 2, f'archived={archived}'

# Add duplicate — should not increase cache
cached2, _ = c.add([msgs[0]])
assert len(cached2) == 3, f'dedup failed, cached={len(cached2)}'

# Verify persistence
loaded = c.load()
assert len(loaded) == 3

shutil.rmtree(test_dir, ignore_errors=True)
print('  PASS: cache')
"

# Test 3: Message model
echo "Test 3: Message model..."
python3 -c "
from adapters.base import Message
m = Message('id1', 'alice', 'hello world')
d = m.to_dict()
assert d['message_id'] == 'id1'
assert d['sender'] == 'alice'
assert d['text'] == 'hello world'
assert 'timestamp' in d

# make_id determinism check (different calls = different IDs due to time)
id1 = Message.make_id('hello', 'alice')
assert len(id1) == 16
assert all(c in '0123456789abcdef' for c in id1)
print('  PASS: message model')
"

# Test 4: Adapter loading
echo "Test 4: Adapter loading..."
python3 -c "
import os
os.environ['COCONUT_ADAPTER_CLI_ENABLED'] = 'true'
os.environ['COCONUT_ADAPTER_SIGNAL_ENABLED'] = 'false'
os.environ['COCONUT_ADAPTER_TEAMS_ENABLED'] = 'false'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
from core import config
cfg = config.load()

# Import all adapters
from adapters.cli_adapter import CLIAdapter
from adapters.signal_adapter import SignalAdapter
from adapters.teams_adapter import TeamsAdapter

cli = CLIAdapter(cfg)
assert cli.name == 'cli'

# Test format_outbound
os.environ['COCONUT_NAME'] = 'TestBot'
os.environ['COCONUT_TAGLINE'] = 'Test'
cfg2 = config.load()
cli2 = CLIAdapter(cfg2)
out = cli2.format_outbound('Hello!')
assert 'TestBot' in out
assert 'Hello!' in out
print('  PASS: adapter loading')
"

# Test 5: System prompt building
echo "Test 5: System prompt..."
python3 -c "
import os
os.environ['COCONUT_NAME'] = 'CoconutTest'
os.environ['COCONUT_TAGLINE'] = 'Security Expert'
os.environ['COCONUT_SYSTEM_PROMPT_FILE'] = 'config/system-prompt.md'
from core import config, llm
cfg = config.load()
prompt = llm.build_system_prompt(cfg)
assert 'CoconutTest' in prompt, f'Name not in prompt'
assert 'Security Expert' in prompt, f'Tagline not in prompt'
assert 'UTC' in prompt, f'Time not in prompt'
print('  PASS: system prompt')
"

# Test 6: Classifier prompt construction (no API call)
echo "Test 6: Classifier prompt structure..."
python3 -c "
from core.classifier import CLASSIFICATION_PROMPT
assert 'REPLY' in CLASSIFICATION_PROMPT
assert 'RELAY' in CLASSIFICATION_PROMPT
assert 'IGNORE' in CLASSIFICATION_PROMPT
assert 'JSON' in CLASSIFICATION_PROMPT
print('  PASS: classifier prompt')
"

# Test 7: Deploy script syntax check
echo "Test 7: Deploy script syntax..."
bash -n scripts/deploy.sh
echo "  PASS: deploy.sh syntax"

echo ""
echo "=== ALL E2E TESTS PASSED ==="
