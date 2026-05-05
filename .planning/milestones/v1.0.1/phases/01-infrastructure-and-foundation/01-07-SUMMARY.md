---
phase: 01-infrastructure-and-foundation
plan: 07
subsystem: railway-deployment
tags: [railway, deployment, infrastructure, docker]
dependency_graph:
  requires: [01-04, 01-05, 01-06]
  provides: [railway-project, production-services]
  affects: []
tech_stack:
  added: []
  patterns: [monorepo-multi-service, root-directory-per-service, shared-env-vars]
key_files:
  created: []
  modified:
    - .env
decisions:
  - "Railway project ID: 246c0b48-d313-45a4-afdc-ea98f0ee99b8"
  - "API service: root /backend, public domain auto-generated, healthcheck on /health"
  - "Scheduler service: root /scheduler, no public domain (internal worker only)"
  - "DATABASE_URL set as shared variable across both services"
  - "Code deployment deferred — services configured but no source connected yet. Will deploy via railway CLI or GitHub integration in Phase 2+"
---

## What was built

Railway project "seva-mining" created with two services: api (root /backend, public domain) and scheduler (root /scheduler, no public domain). Shared DATABASE_URL environment variable configured pointing to Neon pooled connection. Both services show "offline" — ready for code deployment via `railway up` or GitHub repo connection.

## Self-Check: PASSED
