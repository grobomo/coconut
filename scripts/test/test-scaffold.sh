#!/usr/bin/env bash
# T001: Verify project scaffold — all required files exist.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

FAIL=0
check() {
    if [ ! -e "$1" ]; then
        echo "FAIL: missing $1"
        FAIL=1
    else
        echo "OK: $1"
    fi
}

check .github/publish.json
check .github/workflows/secret-scan.yml
check .gitignore
check CLAUDE.md
check TODO.md
check config/coconut.env.example
check config/system-prompt.md
check core/__init__.py
check core/config.py
check core/llm.py
check core/classifier.py
check core/cache.py
check adapters/__init__.py
check adapters/base.py
check adapters/signal_adapter.py
check adapters/teams_adapter.py
check adapters/cli_adapter.py
check coconut.py
check scripts/deploy.sh
check scripts/test/test-scaffold.sh
check specs/001-build-coconut/tasks.md

if [ $FAIL -ne 0 ]; then
    echo "SCAFFOLD TEST FAILED"
    exit 1
fi

echo "ALL SCAFFOLD CHECKS PASSED"
