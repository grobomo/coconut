#!/usr/bin/env bash
# Deploy Coconut to any environment.
# Single script — clones repo, loads env, starts polling.
#
# Usage:
#   bash scripts/deploy.sh                    # Run locally
#   bash scripts/deploy.sh --ccc              # Run via continuous-claude wrapper
#   COCONUT_ENV_FILE=/path/to/coconut.env bash scripts/deploy.sh
#
# All config via env vars or coconut.env file. Zero dependencies beyond Python 3.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COCONUT_ENV_FILE="${COCONUT_ENV_FILE:-$PROJECT_DIR/coconut.env}"
COCONUT_REPO="${COCONUT_REPO:-https://github.com/grobomo/coconut.git}"
COCONUT_BRANCH="${COCONUT_BRANCH:-main}"
CCC_MODE="${1:-}"

# If not in a coconut checkout, clone it
if [ ! -f "$PROJECT_DIR/coconut.py" ]; then
    WORK_DIR="${COCONUT_WORK_DIR:-/tmp/coconut}"
    echo "Cloning coconut to $WORK_DIR..."
    if [ -d "$WORK_DIR/.git" ]; then
        cd "$WORK_DIR" && git pull --ff-only
    else
        git clone --branch "$COCONUT_BRANCH" "$COCONUT_REPO" "$WORK_DIR"
    fi
    PROJECT_DIR="$WORK_DIR"
fi

cd "$PROJECT_DIR"

# Load env file if exists
if [ -f "$COCONUT_ENV_FILE" ]; then
    echo "Loading config from $COCONUT_ENV_FILE"
    set -a
    source "$COCONUT_ENV_FILE"
    set +a
fi

# Validate required vars
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    echo "Set it in env or in $COCONUT_ENV_FILE"
    exit 1
fi

# Check at least one adapter is enabled
if [ "${COCONUT_ADAPTER_SIGNAL_ENABLED:-false}" = "false" ] && \
   [ "${COCONUT_ADAPTER_TEAMS_ENABLED:-false}" = "false" ] && \
   [ "${COCONUT_ADAPTER_CLI_ENABLED:-false}" = "false" ]; then
    echo "ERROR: No adapter enabled. Set COCONUT_ADAPTER_*_ENABLED=true"
    exit 1
fi

echo "Starting Coconut..."
echo "  Poll interval: ${COCONUT_POLL_INTERVAL:-3}s"
echo "  Model: ${COCONUT_MODEL:-claude-haiku-4-5-20251001}"
echo "  Adapters: signal=${COCONUT_ADAPTER_SIGNAL_ENABLED:-false} teams=${COCONUT_ADAPTER_TEAMS_ENABLED:-false} cli=${COCONUT_ADAPTER_CLI_ENABLED:-false}"

if [ "$CCC_MODE" = "--ccc" ]; then
    # Run under continuous-claude — it handles restarts, logging, commits
    CCC_BIN="${CCC_BIN:-continuous-claude}"
    exec "$CCC_BIN" -p "Monitor chats and respond as Coconut. Run: python coconut.py" -m 0 --max-cost 50
else
    # Direct run — just start the Python process
    exec python3 "$PROJECT_DIR/coconut.py"
fi
