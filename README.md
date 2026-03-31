# Coconut

Reusable AI chat assistant that monitors messaging platforms, classifies messages semantically, and responds using the Anthropic API.

## Features

- **Multi-platform** — Signal, Teams, CLI (extensible adapter system)
- **Semantic classification** — LLM-powered REPLY/RELAY/IGNORE routing
- **Zero dependencies** — Python stdlib only, runs anywhere with Python 3.10+
- **Docker ready** — single image, built-in health checks
- **Observable** — per-adapter metrics, token cost tracking, structured JSON logs
- **Configurable** — everything via `COCONUT_*` environment variables

## Quick Start

```bash
# CLI mode (local testing)
COCONUT_ADAPTER_CLI_ENABLED=true \
ANTHROPIC_API_KEY=sk-ant-... \
python coconut.py

# Docker with Signal
cp config/coconut.env.example coconut.env
# Edit coconut.env with your values
docker compose up -d
bash scripts/signal-register.sh +1234567890
```

## Architecture

```
coconut.py           Poll loop, orchestration, signal handling
core/
  config.py          COCONUT_* env var loader
  llm.py             Anthropic API client (retry + backoff)
  classifier.py      Semantic message classifier
  cache.py           Rolling message cache with archiving
  health.py          Health writer, metrics, cost estimation
  quotes.py          Teams quote chain resolution
adapters/
  base.py            Abstract adapter interface (poll/send)
  signal_adapter.py  Signal via signal-cli REST API
  teams_adapter.py   Teams via MS Graph API
  cli_adapter.py     stdin/stdout for testing
```

### Message Flow

```
Adapter.poll() → Cache → Classifier → REPLY: LLM response → Adapter.send()
                                     → RELAY: Forward to external system
                                     → IGNORE: Skip
```

## Configuration

All settings via environment variables. See [`config/coconut.env.example`](config/coconut.env.example) for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Anthropic API key |
| `COCONUT_NAME` | Coconut | Bot display name |
| `COCONUT_MODEL` | claude-haiku-4-5-20251001 | LLM model |
| `COCONUT_POLL_INTERVAL` | 3 | Seconds between polls |
| `COCONUT_ADAPTER_SIGNAL_ENABLED` | false | Enable Signal adapter |
| `COCONUT_ADAPTER_TEAMS_ENABLED` | false | Enable Teams adapter |
| `COCONUT_ADAPTER_CLI_ENABLED` | false | Enable CLI adapter |

## Health Check

```bash
# K8s liveness probe / monitoring
python coconut.py --health
# Exit 0 = healthy, 1 = stale (no heartbeat in 5 min)
# Outputs JSON with uptime, processed count, adapter stats, token cost
```

## Adding an Adapter

1. Create `adapters/your_adapter.py` extending `BaseAdapter`
2. Implement `poll()` → returns `list[Message]`
3. Implement `send(text)` → delivers formatted response
4. Add config loading in `core/config.py` and `coconut.py`

## Tests

```bash
bash scripts/test/test-coconut.sh        # Core E2E (7 tests)
bash scripts/test/test-multi-adapter.sh  # Multi-adapter (6 tests)
bash scripts/test/test-hardening.sh      # Retry, metrics, health (8 tests)
bash scripts/test/test-docker.sh         # Dockerfile validation
```

## License

MIT
