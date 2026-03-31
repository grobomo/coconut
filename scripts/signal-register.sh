#!/usr/bin/env bash
# Register a phone number with signal-cli REST API.
# Run this ONCE after docker-compose up to link your number.
#
# Usage:
#   bash scripts/signal-register.sh +1234567890
#   bash scripts/signal-register.sh +1234567890 --captcha "captcha-string"
#
# After registration, verify with the code Signal sends:
#   bash scripts/signal-register.sh --verify +1234567890 123456

set -euo pipefail

SIGNAL_API_URL="${COCONUT_SIGNAL_CLI_URL:-http://localhost:8080}"
PHONE="${1:?Usage: signal-register.sh +PHONE [--captcha STRING | --verify PHONE CODE]}"
shift || true

case "${1:-register}" in
  --verify)
    VERIFY_PHONE="${2:?Missing phone for verify}"
    CODE="${3:?Missing verification code}"
    echo "Verifying $VERIFY_PHONE with code $CODE..."
    curl -sf -X POST "${SIGNAL_API_URL}/v1/register/${VERIFY_PHONE}/verify/${CODE}" \
      -H 'Content-Type: application/json'
    echo "Verification complete."
    ;;
  --captcha)
    CAPTCHA="${2:?Missing captcha string}"
    echo "Registering $PHONE with captcha..."
    curl -sf -X POST "${SIGNAL_API_URL}/v1/register/${PHONE}" \
      -H 'Content-Type: application/json' \
      -d "{\"captcha\": \"${CAPTCHA}\"}"
    echo "Registration submitted. Check for verification SMS/call."
    ;;
  register|*)
    echo "Registering $PHONE..."
    curl -sf -X POST "${SIGNAL_API_URL}/v1/register/${PHONE}" \
      -H 'Content-Type: application/json'
    echo "Registration submitted. Check for verification SMS/call."
    echo ""
    echo "Next: bash scripts/signal-register.sh --verify $PHONE <CODE>"
    ;;
esac
