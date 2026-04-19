from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.config import Config

router = APIRouter(
    prefix="/config",
    tags=["config"],
    dependencies=[Depends(get_current_user)],
)


class ConfigUpdate(BaseModel):
    value: str


@router.get("")
async def list_config(db: AsyncSession = Depends(get_db)):
    """Return all config key-value pairs."""
    result = await db.execute(select(Config))
    return [{"key": r.key, "value": r.value} for r in result.scalars().all()]


@router.patch("/{key}")
async def update_config(key: str, body: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Upsert a config entry by key (string PK, not UUID)."""
    result = await db.execute(select(Config).where(Config.key == key))
    entry = result.scalar_one_or_none()
    if entry:
        entry.value = body.value
    else:
        entry = Config(key=key, value=body.value)
        db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"key": entry.key, "value": entry.value}


@router.get("/quota")
async def get_quota(db: AsyncSession = Depends(get_db)):
    """Return current Twitter API quota consumption and safety margin from the config table."""
    keys = [
        "twitter_monthly_tweet_count",
        "twitter_quota_safety_margin",
        "twitter_monthly_reset_date",
    ]
    result = await db.execute(select(Config).where(Config.key.in_(keys)))
    rows = {row.key: row.value for row in result.scalars().all()}

    return {
        "monthly_tweet_count": int(rows.get("twitter_monthly_tweet_count", 0)),
        "quota_safety_margin": int(rows.get("twitter_quota_safety_margin", 1500)),
        "monthly_cap": 10000,
        "reset_date": rows.get("twitter_monthly_reset_date"),
    }
