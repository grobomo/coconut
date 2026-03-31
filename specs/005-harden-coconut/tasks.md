# 005 — Harden Coconut

## Phase 1: Reliability

- [ ] T015: Add spec and tasks for hardening work
- [ ] T016: LLM retry with exponential backoff on transient errors (429, 500, 502, 503, 529)
- [ ] T017: Teams refresh token persistence — save rotated tokens to file so restarts don't lose them

**Checkpoint**: `bash scripts/test/test-hardening.sh` — verifies retry logic with mock HTTP server, token file persistence

## Phase 2: Optimization

- [ ] T018: Classifier context window — limit messages sent to LLM to last 15 (not full 50-msg cache)
- [ ] T019: Health check CLI mode — `python coconut.py --health` for K8s liveness probes

**Checkpoint**: `bash scripts/test/test-hardening.sh` — verifies context limiting and health CLI
