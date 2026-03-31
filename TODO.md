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
- [x] T008: Signal deployment — docker-compose.yml, signal-register.sh, signal-list-groups.sh
- [x] T009: Harden — health writer, log-to-file, fix reply-to-all-adapters bug
- [x] T010: Quote chain resolution — port from rone-teams-poller for threaded conversation context
- [ ] T011: Live Signal test — register a phone number, join EP group, test real conversation flow
- [ ] T012: CCC fleet deploy — deploy coconut on AWS CCC worker as persistent service
- [x] T013: RONE poller health check — scripts/k8s/rone-poller-health.sh ready (VPN needed to run)
- [x] T014: Multi-adapter — scripts/test/test-multi-adapter.sh (6/6 tests passing)
- [x] T015: Spec and tasks for hardening (005-harden-coconut)
- [x] T016: LLM retry with exponential backoff on transient errors
- [x] T017: Teams refresh token persistence
- [x] T018: Classifier context window optimization
- [x] T019: Health check CLI mode for K8s liveness probes
- [x] T020: Spec and tasks for polish (006-polish-and-ship)
- [x] T021: Dockerfile — single image, zero pip deps, HEALTHCHECK built-in
- [x] T022: docker-compose builds from Dockerfile
- [x] T023: Per-adapter metrics, poll counts, token cost estimation
- [x] T024: README.md — quickstart, architecture, config reference
- [x] T025: Spec and tasks for webhook adapter + rate limiting (007-webhook-ratelimit)
- [x] T026: Webhook adapter — HTTP server for inbound/outbound messages
- [x] T027: Webhook adapter E2E tests (8/8 passing)
- [x] T028: Per-adapter rate limiter — sliding window, configurable via env vars
- [x] T029: Rate limit tests (8/8 passing)
- [x] T030: Harden webhook (64KB body limit, graceful shutdown) and update README
- [x] T031: GitHub Actions CI — test workflow + secret scan fix
- [x] T032: Fix secret scan false positive in README

- [x] T033: Log rotation — size-based rotation for coconut.log (stdlib only)
- [x] T034: Conversation memory — already works via cache.json persistence (no code needed)
- [x] T035: CLI interactive mode — msvcrt.kbhit() on Windows, threaded pipe reader
- [x] T036: Fix multi-adapter test hang — CLI poll blocks on pipe stdin in test harness
- [x] T037: Update docs — CLAUDE.md, README, TODO with new modules and test counts
- [ ] T038: Slack adapter — Socket Mode + Web API for replies (stdlib only)
- [ ] T039: Slack adapter E2E tests

## Blocked (external deps)
- [ ] T011: Live Signal test — needs user phone number + EP group ID
- [ ] T012: CCC fleet deploy — needs dispatcher repo whitelist update

## Status: In Progress
