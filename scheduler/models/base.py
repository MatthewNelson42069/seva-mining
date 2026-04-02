from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

# Explicit naming conventions prevent unnamed constraints in Alembic migrations.
# Required for Alembic to correctly detect and diff constraints. (D-04, Pattern 1)
# Matches backend/app/models/base.py — must stay in sync.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
