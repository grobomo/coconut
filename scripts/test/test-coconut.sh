#!/usr/bin/env bash
# E2E test: starts coconut with CLI adapter, pipes test messages, verifies output.
# Exit 0 on pass, 1 on fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Coconut E2E Tests ==="
echo ""

# --- Test 1: Config loader ---
echo "[Test 1] Config loader"
RESULT=$(COCONUT_API_KEY=test-key COCONUT_MODEL=test-model python3 -c "
from core import config
cfg = config.load()
print(cfg['COCONUT_API_KEY'], cfg['COCONUT_MODEL'], cfg['COCONUT_ADAPTER'])
")
if echo "$RESULT" | grep -q "test-key test-model cli"; then
    pass "Config loads env vars with defaults"
else
    fail "Config loader returned: $RESULT"
fi

# --- Test 2: Message cache ---
echo "[Test 2] Message cache"
RESULT=$(python3 -c "
from core.cache import MessageCache
c = MessageCache(max_size=3)
c.add({'sender': 'alice', 'text': 'msg1', 'id': '1'})
c.add({'sender': 'bob', 'text': 'msg2', 'id': '2'})
c.add({'sender': 'alice', 'text': 'msg3', 'id': '3'})
c.add({'sender': 'bob', 'text': 'msg4', 'id': '4'})  # triggers trim
print(len(c.messages), c.messages[0]['text'], c.messages[-1]['text'])
dup = c.add({'sender': 'bob', 'text': 'msg4', 'id': '4'})
print('dup:', dup)
")
if echo "$RESULT" | grep -q "3 msg2 msg4" && echo "$RESULT" | grep -q "dup: False"; then
    pass "Cache rolls and deduplicates"
else
    fail "Cache test returned: $RESULT"
fi

# --- Test 3: Adapter loading ---
echo "[Test 3] Adapter loading"
RESULT=$(COCONUT_API_KEY=test python3 -c "
import coconut
from core import config
cfg = config.load()
cfg['COCONUT_ADAPTER'] = 'cli'
a = coconut._get_adapter(cfg)
print(type(a).__name__)
")
if echo "$RESULT" | grep -q "CLIAdapter"; then
    pass "CLI adapter loads correctly"
else
    fail "Adapter test returned: $RESULT"
fi

# --- Test 4: LLM module structure ---
echo "[Test 4] LLM module imports"
RESULT=$(python3 -c "
from core.llm import chat, LLMError, _build_headers
h1 = _build_headers('sk-ant-test123')
h2 = _build_headers('eyJhbGciOiJSUzI1NiJ9.jwt-token')
print('xapi' if 'x-api-key' in h1 else 'no')
print('bearer' if 'authorization' in h2 else 'no')
")
if echo "$RESULT" | grep -q "xapi" && echo "$RESULT" | grep -q "bearer"; then
    pass "LLM handles both key types"
else
    fail "LLM test returned: $RESULT"
fi

# --- Test 5: Classifier module structure ---
echo "[Test 5] Classifier fast-path"
RESULT=$(python3 -c "
from core.classifier import classify
# Fast path: bot's own message should be IGNORE
c, r = classify('dummy', 'dummy', [{'sender': 'Coconut', 'text': 'hi', 'timestamp': ''}])
print(c, r)
# Empty messages
c2, r2 = classify('dummy', 'dummy', [])
print(c2, r2)
")
if echo "$RESULT" | grep -q "IGNORE own message" && echo "$RESULT" | grep -q "IGNORE empty"; then
    pass "Classifier fast-paths work"
else
    fail "Classifier test returned: $RESULT"
fi

# --- Test 6: System prompt loading ---
echo "[Test 6] System prompt"
RESULT=$(COCONUT_API_KEY=test python3 -c "
import coconut
from core import config
cfg = config.load()
prompt = coconut._load_system_prompt(cfg)
print('has_content' if len(prompt) > 50 else 'empty')
print('coconut' if 'Coconut' in prompt else 'no_name')
")
if echo "$RESULT" | grep -q "has_content" && echo "$RESULT" | grep -q "coconut"; then
    pass "System prompt loads from file"
else
    fail "System prompt test returned: $RESULT"
fi

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ $FAIL -gt 0 ]; then
    exit 1
fi
exit 0
