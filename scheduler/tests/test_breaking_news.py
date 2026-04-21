"""Wave-0 stub for sub-agent tests. Real tests added once module exists."""
import pytest

pytest.importorskip("agents.content.breaking_news",
                    reason="Sub-agent module not yet created (Wave 0)")

# NOTE: lazy-import inside tests, not at module top, so pytest collection
# never fails even when the module is absent. Real test bodies replace
# this file in Task 5 (per-agent split).


def test_module_placeholder():
    pytest.skip("Replaced in Task 5 per-agent test split")
