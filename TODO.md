# Coconut — Reusable AI Chat Assistant

## Vision
Extract Coconut from hackathon26's RONE poller into a standalone, modular AI assistant that:
- Monitors chat platforms (Signal, Teams) with 3s polling
- Semantic analysis on conversation history (like rone-teams-poller classifier)
- Classifies messages as REPLY/RELAY/IGNORE using LLM
- Responds as "Coconut" persona via Anthropic API
- Deploys anywhere with a single script via CCC (continuous-claude)
- Unix principles: small composable pieces, everything configurable via env vars, APIs always

## Source Code
Extracted and modularized from:
- `rone-teams-poller/k8s/poller-script.py` (polling, cache, quote chains)
- `rone-teams-poller/k8s/ccc-worker-script.py` (LLM worker, Coconut persona)
- `rone-teams-poller/scripts/classify.py` (semantic message classification)
- `hackathon26/scripts/team-chat.py` (outbound messaging)

## Tasks

- [x] T001: Project scaffold — .github, config, gitignore, publish.json, CLAUDE.md
- [x] T002: Core module — config loader, LLM client, message classifier, response generator
- [x] T003: Adapters — Signal adapter (signal-cli REST API), Teams adapter (Graph API), CLI adapter
- [x] T004: Polling loop — main event loop with 3s poll, message cache, semantic analysis
- [x] T005: Deploy script — single `scripts/deploy.sh` that launches coconut on CCC
- [x] T006: System prompt & persona — configurable identity, domain knowledge (TrendAI Technical Advisor)
- [x] T007: E2E test — scripts/test/test-coconut.sh exercises full pipeline with CLI adapter
- [x] T008: Signal deployment — docker-compose.yml, signal-register.sh, signal-list-groups.sh (merged to main)
- [x] T009: Harden — health writer, log-to-file, fix reply-to-all-adapters bug
- [x] T010: Quote chain resolution — port from rone-teams-poller for threaded conversation context
- [ ] T011: Live Signal test — register a phone number, join EP group, test real conversation flow
- [ ] T012: CCC fleet deploy — deploy coconut on AWS CCC worker as persistent service
- [x] T013: RONE poller health check — scripts/k8s/rone-poller-health.sh ready (VPN needed to run)
- [x] T014: Multi-adapter — scripts/test/test-multi-adapter.sh (6/6 tests passing)
- [ ] T015: Spec and tasks for hardening (005-harden-coconut)
- [ ] T016: LLM retry with exponential backoff on transient errors
- [ ] T017: Teams refresh token persistence
- [ ] T018: Classifier context window optimization
- [ ] T019: Health check CLI mode for K8s liveness probes

## Status: In Progress
