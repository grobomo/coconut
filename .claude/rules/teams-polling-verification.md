# Teams Chat Polling Verification

When working on the Teams adapter or deploying coconut with Teams enabled:
- Verify Teams polling works by checking health.json for teams adapter stats
- Run `bash scripts/test/test-multi-adapter.sh` to validate adapter loading and routing
- For live testing, check that `adapters.teams.polls` increments in health output
