#!/usr/bin/env bash
# List Signal groups for a registered number.
# Use this to find the group ID for your coconut.env config.
#
# Usage: bash scripts/signal-list-groups.sh +1234567890

set -euo pipefail

SIGNAL_API_URL="${COCONUT_SIGNAL_CLI_URL:-http://localhost:8080}"
PHONE="${1:?Usage: signal-list-groups.sh +PHONE}"

echo "Groups for $PHONE:"
curl -sf "${SIGNAL_API_URL}/v1/groups/${PHONE}" | python3 -c "
import json, sys
groups = json.load(sys.stdin)
if not groups:
    print('  (no groups)')
    sys.exit(0)
for g in groups:
    gid = g.get('id', g.get('internal_id', '?'))
    name = g.get('name', '(unnamed)')
    members = len(g.get('members', []))
    print(f'  {name} ({members} members)')
    print(f'    ID: {gid}')
"
