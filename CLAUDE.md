# Coconut -- Reusable AI Chat Assistant

## What This Is
Modular AI chat assistant that monitors messaging platforms (Signal, Teams) with configurable polling and semantic message classification. Python stdlib only, zero dependencies.

## Architecture

```
coconut.py              Main polling loop (entry point)
core/
  config.py             Env var loader (COCONUT_* prefix)
  llm.py                Anthropic API client (urllib, no deps)
  classifier.py         Semantic message classifier (REPLY/RELAY/IGNORE)
  cache.py              Rolling message cache with overflow archiving
adapters/
  base.py               Abstract adapter interface
  signal_adapter.py     Signal via signal-cli REST API
  teams_adapter.py      Teams via MS Graph API (refresh token flow)
  cli_adapter.py        stdin/stdout for testing
config/
  coconut.env.example   Example env vars
  system-prompt.md      Default persona
scripts/
  deploy.sh             Deploy to CCC environment
  test/test-coconut.sh  E2E test with CLI adapter
```

## Key Design Decisions
- Python stdlib ONLY -- no pip, no requirements.txt
- All config via COCONUT_* env vars
- Each file under 200 lines
- Adapters are pluggable: add new platforms by implementing base.py interface
- LLM client supports both sk-ant API keys and OAuth JWTs

## Running
```bash
# With CLI adapter (testing)
COCONUT_ADAPTER=cli COCONUT_API_KEY=sk-ant-... python coconut.py

# With Signal
COCONUT_ADAPTER=signal COCONUT_SIGNAL_CLI_URL=http://localhost:8080 \
  COCONUT_SIGNAL_GROUP_ID=group123 COCONUT_API_KEY=sk-ant-... python coconut.py
```

## Testing
```bash
bash scripts/test/test-coconut.sh
```
