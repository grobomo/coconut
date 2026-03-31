#!/usr/bin/env bash
# T033: Log rotation tests
set -euo pipefail
cd "$(dirname "$0")/../.."

PASS=0; FAIL=0
pass() { PASS=$((PASS+1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }

echo "=== Log Rotation Tests ==="

# Test 1: RotatingLog creates file and writes
echo "Test 1: Basic write..."
python3 -c "
import os, tempfile, shutil
from core.logrotate import RotatingLog

d = tempfile.mkdtemp()
try:
    log = RotatingLog(os.path.join(d, 'test.log'), max_bytes=1000, backups=2)
    log.write('hello\n')
    log.flush()
    assert os.path.exists(os.path.join(d, 'test.log'))
    with open(os.path.join(d, 'test.log')) as f:
        assert f.read() == 'hello\n'
    log.close()
    print('OK')
finally:
    shutil.rmtree(d)
" && pass "basic write" || fail "basic write"

# Test 2: Rotation triggers at size threshold
echo "Test 2: Rotation triggers..."
python3 -c "
import os, tempfile, shutil
from core.logrotate import RotatingLog

d = tempfile.mkdtemp()
try:
    log = RotatingLog(os.path.join(d, 'test.log'), max_bytes=100, backups=2)
    # Write ~80 chars
    log.write('A' * 80 + '\n')
    log.flush()

    # Write another ~80 — should trigger rotation
    log.write('B' * 80 + '\n')
    log.flush()
    assert os.path.exists(os.path.join(d, 'test.log.1')), 'test.log.1 not created'
    # .1 should have the old content (A's)
    with open(os.path.join(d, 'test.log.1')) as f:
        assert 'A' * 80 in f.read()
    # Current log should have new content (B's)
    with open(os.path.join(d, 'test.log')) as f:
        assert 'B' * 80 in f.read()
    log.close()
    print('OK')
finally:
    shutil.rmtree(d)
" && pass "rotation triggers" || fail "rotation triggers"

# Test 3: Backup limit respected
echo "Test 3: Backup limit..."
python3 -c "
import os, tempfile, shutil
from core.logrotate import RotatingLog

d = tempfile.mkdtemp()
try:
    log = RotatingLog(os.path.join(d, 'test.log'), max_bytes=50, backups=2)
    for i in range(5):
        log.write(f'round-{i}-' + 'X' * 45 + '\n')
        log.flush()
    log.close()

    # Should have current + .1 + .2 only (backups=2)
    assert os.path.exists(os.path.join(d, 'test.log'))
    assert os.path.exists(os.path.join(d, 'test.log.1'))
    assert os.path.exists(os.path.join(d, 'test.log.2'))
    assert not os.path.exists(os.path.join(d, 'test.log.3')), '.log.3 should not exist'
    print('OK')
finally:
    shutil.rmtree(d)
" && pass "backup limit" || fail "backup limit"

# Test 4: Zero backups = no rotation files kept
echo "Test 4: Zero backups..."
python3 -c "
import os, tempfile, shutil
from core.logrotate import RotatingLog

d = tempfile.mkdtemp()
try:
    log = RotatingLog(os.path.join(d, 'test.log'), max_bytes=50, backups=0)
    log.write('A' * 60 + '\n')
    log.flush()
    log.write('B' * 60 + '\n')
    log.flush()
    log.close()

    assert os.path.exists(os.path.join(d, 'test.log'))
    assert not os.path.exists(os.path.join(d, 'test.log.1')), 'no backups should exist'
    print('OK')
finally:
    shutil.rmtree(d)
" && pass "zero backups" || fail "zero backups"

# Test 5: Integration — coconut.py imports RotatingLog
echo "Test 5: Integration import..."
python3 -c "
import ast
with open('coconut.py') as f:
    tree = ast.parse(f.read())
imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
found = any(
    n.module == 'core.logrotate' and any(a.name == 'RotatingLog' for a in n.names)
    for n in imports
)
assert found, 'coconut.py must import RotatingLog from core.logrotate'
print('OK')
" && pass "integration import" || fail "integration import"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
