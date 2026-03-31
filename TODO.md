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
- [ ] T008: Signal deployment — set up signal-cli-rest-api, register number, connect to EP group
- [x] T009: Harden — health writer, log-to-file, fix reply-to-all-adapters bug
- [x] T010: Quote chain resolution — port from rone-teams-poller for threaded conversation context

## Session Handoff (2026-03-31)

### Done this session
- Built entire coconut project from scratch — 15 files, all core modules
- core/: config, llm, classifier, cache, health, quotes (6 modules)
- adapters/: Signal, Teams, CLI (3 adapters + base)
- coconut.py: main poll loop with health heartbeat, log-to-file
- scripts/deploy.sh: single-command deploy (local or --ccc mode)
- 7 passing E2E tests
- GitHub repo created: grobomo/coconut (public)
- Bug fixed: replies now route to source adapter only (not all)
- Quote chain resolution ported from rone-teams-poller

### Remaining
- T008: Signal deployment — need signal-cli-rest-api running + user's Signal group ID with EP
- Merge 001-T001-scaffold branch → 001-build-coconut → main
- Test with real Anthropic API key (all tests use mocks so far)
- RONE teams poller may be dead — user mentioned "haven't checked if it still exists"

## Status: In Progress
