"""add feature engineering and baseline fields

Revision ID: e9b21457b5e2
Revises: b726294cde40
Create Date: 2026-09-17 01:25:53.192114

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9b21457b5e2"
down_revision: str | None = "b726294cde40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# NOTE: alembic --autogenerate also proposed dropping `checkpoints`/`checkpoint_writes`/
# `checkpoint_blobs`/`checkpoint_migrations` — those are LangGraph's own tables (see
# b726294cde40's note) — removed by hand, same as last time.

_NEW_DECISION_KINDS = [
    "TARGET_CONFIRMATION",
    "PLAN_APPROVAL",
    "FEATURE_ENGINEERING_APPROVAL",
    "BASELINE_APPROVAL",
]


def upgrade() -> None:
    op.alter_column(
        "decisions",
        "kind",
        existing_type=sa.VARCHAR(length=19),
        type_=sa.Enum(*_NEW_DECISION_KINDS, name="decisionkind", native_enum=False),
        existing_nullable=False,
    )
    op.add_column(
        "sessions", sa.Column("pipeline_storage_key", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sessions", "pipeline_storage_key")
    op.alter_column(
        "decisions",
        "kind",
        existing_type=sa.Enum(*_NEW_DECISION_KINDS, name="decisionkind", native_enum=False),
        type_=sa.VARCHAR(length=19),
        existing_nullable=False,
    )
