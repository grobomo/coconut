#!/usr/bin/env bash
# Deploy Coconut to a CCC environment.
# Usage: COCONUT_API_KEY=sk-ant-... ./scripts/deploy.sh [adapter]
#
# Clones repo (or pulls latest), copies env, starts coconut.py.
# Keeps running via nohup. Logs to coconut.log.

set -euo pipefail

ADAPTER="${1:-${COCONUT_ADAPTER:-cli}}"
REPO_URL="${COCONUT_REPO_URL:-https://github.com/grobomo/coconut.git}"
DEPLOY_DIR="${COCONUT_DEPLOY_DIR:-$HOME/coconut}"
LOG_FILE="$DEPLOY_DIR/coconut.log"
PID_FILE="$DEPLOY_DIR/coconut.pid"

echo "[deploy] Deploying coconut with adapter=$ADAPTER"

# Clone or update
if [ -d "$DEPLOY_DIR/.git" ]; then
    echo "[deploy] Updating existing install..."
    cd "$DEPLOY_DIR"
    git pull --ff-only origin main 2>/dev/null || git pull --ff-only origin 001-build-coconut
else
    echo "[deploy] Cloning fresh..."
    git clone "$REPO_URL" "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi

# Stop existing instance
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[deploy] Stopping existing instance (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# Copy env file if provided
if [ -f "$HOME/.coconut.env" ]; then
    cp "$HOME/.coconut.env" "$DEPLOY_DIR/coconut.env"
    echo "[deploy] Copied ~/.coconut.env"
fi

# Export adapter
export COCONUT_ADAPTER="$ADAPTER"

# Start
echo "[deploy] Starting coconut..."
nohup python3 "$DEPLOY_DIR/coconut.py" > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

echo "[deploy] Started (PID $(cat "$PID_FILE"), log: $LOG_FILE)"
echo "[deploy] Monitor: tail -f $LOG_FILE"
