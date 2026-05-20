"""v3.1 Phase 12 — Per-tenant Anthropic API key resolver.

Every production Anthropic client instantiation in the scheduler routes
through `get_anthropic_client(company_id)` so that Seva's LLM calls bill
to SEVA_ANTHROPIC_API_KEY and Juno's calls bill to JUNO_ANTHROPIC_API_KEY.

Fallback policy (D-01): when the per-tenant env var is unset, fall back
to the shared ANTHROPIC_API_KEY and emit ONE logger.warning per
company_id per process lifetime. Subsequent calls reuse the cached client
silently. If shared ANTHROPIC_API_KEY is ALSO unset, scheduler boot fails
(existing failure mode preserved at Settings() instantiation).

Strict mode (D-02): when settings.anthropic_resolver_strict is True, the
resolver RAISES RuntimeError instead of falling back. Flip this on in
Railway AFTER per-tenant keys are confirmed working.

Pattern mirrors scheduler/queries/scoped.py: shared helper module above
per-feature agent dirs, single function export, module-level cache.

CI grep gate scripts/verify-anthropic-resolver.sh enforces that this is
the ONLY production site that constructs the AsyncAnthropic SDK class.
"""
from __future__ import annotations

import logging
from typing import Literal

from anthropic import AsyncAnthropic

from config import get_settings

logger = logging.getLogger(__name__)


# Process-lifetime cache. Keyed on (company_id, timeout) — different
# callers requesting different timeouts get different client instances
# (different timeout = different AsyncAnthropic constructor args).
_client_cache: dict[tuple[str, float], AsyncAnthropic] = {}

# Tracks which company_ids have already logged a fallback WARN this
# process. Reset only by process restart (D-01: WARN-once semantics).
_warned_companies: set[str] = set()


def get_anthropic_client(
    company_id: Literal["seva", "juno"],
    *,
    timeout: float = 60.0,
) -> AsyncAnthropic:
    """Resolve the per-tenant Anthropic client for `company_id`.

    Args:
        company_id: "seva" or "juno" — hardcoded literal at call sites per D-07.
        timeout: Forwarded to AsyncAnthropic constructor. Default 60.0s
            matches the daily_summary.py Sonnet baseline.

    Returns:
        AsyncAnthropic instance. Same `(company_id, timeout)` returns the
        same cached instance for the process lifetime.

    Raises:
        RuntimeError: if `anthropic_resolver_strict=True` AND the per-tenant
            env var is unset. Also raises (indirectly via Settings()) if the
            shared ANTHROPIC_API_KEY is unset at scheduler boot.
    """
    cache_key = (company_id, timeout)
    if cache_key in _client_cache:
        cached = _client_cache[cache_key]
        _log_call(company_id, cached.api_key)
        return cached

    settings = get_settings()
    per_tenant_attr = f"{company_id}_anthropic_api_key"
    per_tenant_key: str | None = getattr(settings, per_tenant_attr, None)

    if per_tenant_key:
        api_key = per_tenant_key
        key_source = f"{company_id.upper()}_ANTHROPIC_API_KEY"
    else:
        if settings.anthropic_resolver_strict:
            raise RuntimeError(
                f"ANTHROPIC_RESOLVER_STRICT=true but "
                f"{company_id.upper()}_ANTHROPIC_API_KEY unset; "
                f"refusing to fall back to shared key"
            )
        api_key = settings.anthropic_api_key
        key_source = "ANTHROPIC_API_KEY (fallback)"
        if company_id not in _warned_companies:
            logger.warning(
                "anthropic_resolver fallback: %s_ANTHROPIC_API_KEY unset, "
                "using shared ANTHROPIC_API_KEY for company_id=%s",
                company_id.upper(),
                company_id,
            )
            _warned_companies.add(company_id)

    client = AsyncAnthropic(api_key=api_key, timeout=timeout)
    _client_cache[cache_key] = client
    logger.info(
        "anthropic_resolver: instantiated client for company_id=%s key_source=%s timeout=%.1fs",
        company_id,
        key_source,
        timeout,
    )
    _log_call(company_id, api_key)
    return client


# 'model' intentionally omitted — resolver does not know caller's model choice;
# downstream sites can wrap with structlog if model attribution is needed.
def _log_call(company_id: str, api_key: str) -> None:
    """Emit the per-call structured log for cost-attribution observability.

    Fingerprint is last 8 chars of api_key (matches Anthropic console's
    truncated display format) — NEVER log the full key. Per D-03.
    """
    fingerprint = api_key[-8:] if len(api_key) >= 8 else "short_key"
    logger.info(
        "anthropic_call event=%s company=%s key_fingerprint=%s",
        "anthropic_call",
        company_id,
        fingerprint,
    )
