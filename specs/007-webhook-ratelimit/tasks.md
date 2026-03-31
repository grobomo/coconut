# 007 — Webhook Adapter + Rate Limiting

## Phase 1: Spec

- [x] T025: Spec and tasks for webhook adapter + rate limiting

**Checkpoint**: `bash scripts/test/test-coconut.sh` — existing tests still pass

## Phase 2: Webhook Adapter

- [ ] T026: Webhook adapter — HTTP server that receives POST messages and sends replies via callback URL
- [ ] T027: Webhook adapter tests — E2E test with mock HTTP client

**Checkpoint**: `bash scripts/test/test-webhook.sh` — webhook adapter receives, classifies, and responds

## Phase 3: Rate Limiting

- [ ] T028: Per-adapter rate limiter — sliding window token bucket, configurable via env vars
- [ ] T029: Rate limit tests — verify throttling and burst handling

**Checkpoint**: `bash scripts/test/test-ratelimit.sh` — rate limiter blocks excess messages, passes within limit
