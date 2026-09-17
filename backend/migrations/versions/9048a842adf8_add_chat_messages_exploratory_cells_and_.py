"""add chat messages, exploratory cells, and expertise level

Revision ID: 9048a842adf8
Revises: e9b21457b5e2
Create Date: 2026-09-17 02:36:36.508832

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9048a842adf8"
down_revision: str | None = "e9b21457b5e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# NOTE: alembic --autogenerate also proposed dropping `checkpoints`/`checkpoint_writes`/
# `checkpoint_blobs`/`checkpoint_migrations` — LangGraph's own tables, not ours; see
# b726294cde40's note. Removed by hand, same as every migration since.


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column(
            "role", sa.Enum("USER", "ASSISTANT", name="chatrole", native_enum=False), nullable=False
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("referenced_cell_ids", sa.JSON(), nullable=True),
        sa.Column("exploratory_cell_id", sa.String(length=36), nullable=True),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["exploratory_cell_id"], ["notebook_cells.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"], unique=False
    )
    op.add_column(
        "notebook_cells",
        sa.Column("is_exploratory", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "expertise_level",
            sa.Enum("BEGINNER", "INTERMEDIATE", "EXPERT", name="expertiselevel", native_enum=False),
            nullable=False,
            server_default="INTERMEDIATE",
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "expertise_level")
    op.drop_column("notebook_cells", "is_exploratory")
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
