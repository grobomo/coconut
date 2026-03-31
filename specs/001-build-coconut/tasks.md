# 001 — Build Coconut

## Phase 1: Scaffold

- [ ] T001: Project scaffold — .github, config, gitignore, publish.json, CLAUDE.md

**Checkpoint**: `bash scripts/test/test-scaffold.sh` — verifies all required files exist

## Phase 2: Core

- [ ] T002: Core module — config loader, LLM client, message classifier, response generator
- [ ] T003: Adapters — Signal adapter (signal-cli REST API), Teams adapter (Graph API), CLI adapter

**Checkpoint**: `bash scripts/test/test-core.sh` — imports all modules, runs classifier on sample messages

## Phase 3: Runtime

- [ ] T004: Polling loop — main event loop with 3s poll, message cache, semantic analysis
- [ ] T005: Deploy script — single `scripts/deploy.sh` that launches coconut on CCC

**Checkpoint**: `bash scripts/test/test-polling.sh` — starts coconut with CLI adapter, sends 3 messages, verifies responses

## Phase 4: Polish

- [ ] T006: System prompt & persona — configurable identity, domain knowledge (TrendAI Technical Advisor)
- [ ] T007: E2E test — scripts/test/test-coconut.sh exercises full pipeline with CLI adapter

**Checkpoint**: `bash scripts/test/test-coconut.sh` — full e2e with persona verification
