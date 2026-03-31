# 006 — Polish and Ship

## Phase 1: Packaging

- [ ] T020: Spec and tasks for polish work
- [ ] T021: Dockerfile — single image with coconut, no external deps
- [ ] T022: Update docker-compose.yml to build from Dockerfile instead of python:3.12-slim

**Checkpoint**: `bash scripts/test/test-docker.sh` — builds image, runs health check inside container

## Phase 2: Observability

- [ ] T023: Metrics endpoint — /metrics with uptime, token cost, messages processed, adapter status

**Checkpoint**: `bash scripts/test/test-hardening.sh` — extended with metrics verification

## Phase 3: Documentation

- [ ] T024: README.md — quickstart, architecture diagram (text), config reference

**Checkpoint**: `bash scripts/test/test-scaffold.sh` — updated to verify README exists with required sections
