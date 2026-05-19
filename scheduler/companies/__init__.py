"""Scheduler-side tenant identity (mirrors backend/app/companies/__init__.py
per Phase B dual-model parity, see 09-CONTEXT.md D-03).

v3.0 Phase 9 — Multi-tenant foundation. The hardcoded ``Literal["seva", "juno"]``
and the matching ``ACTIVE_COMPANIES`` tuple replace a ``companies`` DB table for
v3.0 (accepted tech debt; close in v3.2+ when N>2 tenants requires a real table —
tracked in REQUIREMENTS.md → TENANT-N-v32).

The CHECK constraint at the DB layer (Alembic 0014 ``ck_<table>_company_id``)
MUST stay in lockstep with ``ACTIVE_COMPANIES`` below — and with the matching
constant in ``backend/app/companies/__init__.py``. Adding a new tenant in v3.0
requires editing BOTH Python files + an Alembic migration that rewrites the
CHECK.
"""
from typing import Literal

CompanyId = Literal["seva", "juno"]

ACTIVE_COMPANIES: tuple[CompanyId, ...] = ("seva", "juno")

__all__ = ["CompanyId", "ACTIVE_COMPANIES"]
