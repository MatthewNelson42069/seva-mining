# Import all models here to register them with Base.metadata.
# Alembic env.py imports this module — all models must be imported before
# target_metadata is read. Missing imports = empty autogenerate migration. (Pitfall 5)
from app.models.agent_run import AgentRun
from app.models.base import Base
from app.models.config import Config
from app.models.content_bundle import ContentBundle
from app.models.daily_digest import DailyDigest
from app.models.draft_item import DraftItem, DraftStatus
from app.models.keyword import Keyword
from app.models.market_snapshot import MarketSnapshot
from app.models.watchlist import Watchlist

__all__ = [
    "Base",
    "DraftItem", "DraftStatus",
    "ContentBundle",
    "AgentRun",
    "DailyDigest",
    "Watchlist",
    "Keyword",
    "Config",
    "MarketSnapshot",
]
