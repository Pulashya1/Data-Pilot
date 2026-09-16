"""add auto_decide and widen agent_status for waiting_decision

Revision ID: b726294cde40
Revises: ce716a221364
Create Date: 2026-09-16 16:37:53.212304

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b726294cde40"
down_revision: str | None = "ce716a221364"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# NOTE: alembic --autogenerate also proposed dropping `checkpoints`/`checkpoint_writes`/
# `checkpoint_blobs`/`checkpoint_migrations` — those are LangGraph's own tables, created by
# `AsyncPostgresSaver.setup()` at app startup (app/agent/checkpoint.py), not by our SQLAlchemy
# `Base.metadata`. Autogenerate always flags them as "unknown to the model"; dropping them here
# would wipe every session's in-flight agent-run checkpoints, so that part of the diff was
# removed by hand — don't regenerate this file without excluding those tables again.


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("auto_decide", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column(
        "sessions",
        "agent_status",
        existing_type=sa.VARCHAR(length=11),
        type_=sa.Enum(
            "NOT_STARTED",
            "RUNNING",
            "WAITING_DECISION",
            "DONE",
            "ERROR",
            name="agentstatus",
            native_enum=False,
        ),
        existing_nullable=False,
        existing_server_default=sa.text("'NOT_STARTED'::character varying"),
    )


def downgrade() -> None:
    op.alter_column(
        "sessions",
        "agent_status",
        existing_type=sa.Enum(
            "NOT_STARTED",
            "RUNNING",
            "WAITING_DECISION",
            "DONE",
            "ERROR",
            name="agentstatus",
            native_enum=False,
        ),
        type_=sa.VARCHAR(length=11),
        existing_nullable=False,
        existing_server_default=sa.text("'NOT_STARTED'::character varying"),
    )
    op.drop_column("sessions", "auto_decide")
