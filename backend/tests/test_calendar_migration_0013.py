"""Migration 0013 static checks — verifies the migration file declares the
correct revision chain and the expected DDL operations. Full upgrade/downgrade
round-trip is verified manually with a real Postgres dev DB (see plan
acceptance criteria); SQLite in-memory does not support every Postgres DDL
primitive we use.
"""
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parent.parent
    / "alembic"
    / "versions"
    / "0013_calendar_title_nullable_unique_date.py"
)


def test_migration_0013_revision_chain():
    content = MIGRATION_PATH.read_text()
    assert 'revision = "0013"' in content
    assert 'down_revision = "0012"' in content


def test_migration_0013_upgrade_alters_title_nullable():
    content = MIGRATION_PATH.read_text()
    assert "alter_column" in content
    assert '"title"' in content
    assert "nullable=True" in content


def test_migration_0013_upgrade_adds_unique_date_constraint():
    content = MIGRATION_PATH.read_text()
    assert "create_unique_constraint" in content
    assert '"uq_calendar_items_date"' in content
    assert '["date"]' in content


def test_migration_0013_downgrade_reverses_changes():
    content = MIGRATION_PATH.read_text()
    assert "drop_constraint" in content
    # downgrade must restore title NOT NULL
    downgrade_section = content.split("def downgrade()", 1)[1]
    assert "nullable=False" in downgrade_section
