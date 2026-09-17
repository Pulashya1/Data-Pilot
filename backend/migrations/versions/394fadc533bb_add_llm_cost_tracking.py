"""add llm cost tracking

Revision ID: 394fadc533bb
Revises: 9048a842adf8
Create Date: 2026-09-17 12:28:05.812535

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "394fadc533bb"
down_revision: str | None = "9048a842adf8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# NOTE: alembic --autogenerate also proposed dropping `checkpoints`/`checkpoint_writes`/
# `checkpoint_blobs`/`checkpoint_migrations` — LangGraph's own tables, not ours; see
# b726294cde40's note. Removed by hand, same as every migration since.


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("llm_cost_used_usd", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sessions", "llm_cost_used_usd")
