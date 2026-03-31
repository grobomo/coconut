# Coconut — Reusable AI Chat Assistant

Monitors messaging platforms (Signal, Teams) with semantic analysis. Deploys anywhere via CCC.

## Architecture

```
coconut.py          Main entry point — poll loop, orchestration
core/
  config.py         Env var loader (COCONUT_* prefix)
  llm.py            Anthropic API client (stdlib only)
  classifier.py     Semantic message classifier (REPLY/RELAY/IGNORE)
  cache.py          Rolling message cache with archiving
adapters/
  base.py           Abstract adapter interface
  signal_adapter.py Signal via signal-cli REST API
  teams_adapter.py  Teams via MS Graph API
  cli_adapter.py    stdin/stdout for testing
config/
  coconut.env.example  Example configuration
  system-prompt.md     Default persona
scripts/
  deploy.sh         Single-command CCC deployment
  test/              E2E tests
```

## Principles
- Python stdlib only — zero dependencies
- Every value from env vars — no hardcoded anything
- Each file under 200 lines
- Unix: small composable modules, pipes, APIs

## Running
```bash
# Local with CLI adapter
COCONUT_ADAPTER_CLI_ENABLED=true python coconut.py

# With Signal
COCONUT_ADAPTER_SIGNAL_ENABLED=true \
COCONUT_SIGNAL_CLI_URL=http://localhost:8080 \
COCONUT_SIGNAL_GROUP_ID=your-group-id \
ANTHROPIC_API_KEY=$YOUR_KEY \
python coconut.py

# Deploy to CCC
bash scripts/deploy.sh
```

## Config
All configuration via `COCONUT_*` environment variables. See `config/coconut.env.example`.
