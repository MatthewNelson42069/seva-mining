# Phase 1: Infrastructure and Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 01-infrastructure-and-foundation
**Areas discussed:** Project structure, DB migration strategy, Railway deployment, WhatsApp templates
**Mode:** Auto (all recommended defaults selected)

---

## Project Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Monorepo | Single repo with /backend and /frontend dirs | ✓ |
| Separate repos | Backend and frontend in separate git repos | |
| Backend-only initially | Frontend added later in separate repo | |

**User's choice:** [auto] Monorepo (recommended default)
**Notes:** Simpler ops, single git history, Railway deploys both from same repo

---

## DB Migration Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Manual with auto-gen starting point | Auto-generate then review/edit before applying | ✓ |
| Pure auto-generation | Trust Alembic to generate correct migrations | |
| Fully manual | Write all migrations by hand | |

**User's choice:** [auto] Manual with auto-generation (recommended default)
**Notes:** More control over indexes, enums, and constraint naming

---

## Railway Deployment

| Option | Description | Selected |
|--------|-------------|----------|
| Two services, same repo | Different start commands, shared codebase | ✓ |
| Two repos | Separate deployment pipelines | |
| Single service with process manager | One Railway service running both processes | |

**User's choice:** [auto] Two services from same repo (recommended default)
**Notes:** Simplest Railway setup, avoids single-point-of-failure

---

## WhatsApp Templates

| Option | Description | Selected |
|--------|-------------|----------|
| Structured with variable placeholders | Dynamic content via Twilio variables | ✓ |
| Static text templates | Fixed messages with no dynamic content | |

**User's choice:** [auto] Structured templates with variables (recommended default)
**Notes:** Three templates: morning digest, breaking alert, expiry alert

---

## Claude's Discretion

- Alembic configuration details (naming conventions, migration template)
- Dockerfile base image selection and layer optimization
- PostgreSQL advisory lock implementation details
- Railway service naming and configuration specifics

## Deferred Ideas

None — discussion stayed within phase scope
