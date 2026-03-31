---
phase: 01-infrastructure-and-foundation
plan: 03
subsystem: config-database-models
tags: [pydantic-settings, sqlalchemy, asyncpg, neon, models]
dependency_graph:
  requires: [01-02]
  provides: [config-layer, async-engine, orm-models]
  affects: [01-04, 01-05, 01-06]
tech_stack:
  added: [pydantic-settings-2.x, python-dotenv-1.x]
  patterns: [pydantic-settings-env-config, async-engine-with-neon-pooling, sqlalchemy-2.0-declarative, jsonb-for-alternatives]
key_files:
  created:
    - backend/app/__init__.py
    - backend/app/config.py
    - backend/app/database.py
    - backend/app/models/__init__.py
    - backend/app/models/base.py
    - backend/app/models/draft_item.py
    - backend/app/models/content_bundle.py
    - backend/app/models/agent_run.py
    - backend/app/models/daily_digest.py
    - backend/app/models/watchlist.py
    - backend/app/models/keyword.py
    - scheduler/config.py
    - scheduler/database.py
  modified:
    - backend/tests/test_config.py
    - backend/tests/test_database.py
decisions:
  - "pool_pre_ping=True and pool_recycle=300 for Neon serverless cold starts"
  - "DraftStatus enum: pending, approved, edited_approved, rejected, expired"
  - "JSONB for sources arrays, analytics_snapshot, infographic_brief"
  - "Naming convention for SQLAlchemy constraints for Alembic auto-generation"
---

## What was built

Pydantic-settings configuration layer (14 environment variables), SQLAlchemy async database engine with Neon-specific pool parameters, and all 6 ORM models: DraftItem, ContentBundle, AgentRun, DailyDigest, Watchlist, Keyword. Scheduler service gets its own config and engine. 5/5 tests GREEN.

## Self-Check: PASSED
