"""add users and login tokens for magic link auth

Revision ID: 17c1c344060c
Revises: 394fadc533bb
Create Date: 2026-09-17 14:55:16.488984

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "17c1c344060c"
down_revision: str | None = "394fadc533bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOTE: autogenerate also proposed dropping `checkpoint_blobs`/`checkpoint_writes`/
    # `checkpoints`/`checkpoint_migrations` — those are LangGraph's own tables, created at
    # runtime by `AsyncPostgresSaver.setup()` (app/agent/checkpoint.py), not part of this
    # project's SQLAlchemy `Base.metadata`. Autogenerate always flags them as "unknown" and
    # would drop them; removed from this migration by hand.
    op.create_table(
        "login_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_login_tokens_email"), "login_tokens", ["email"], unique=False)
    op.create_index(op.f("ix_login_tokens_token_hash"), "login_tokens", ["token_hash"], unique=True)
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.add_column("sessions", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_foreign_key(None, "sessions", "users", ["user_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint(None, "sessions", type_="foreignkey")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_column("sessions", "user_id")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_login_tokens_token_hash"), table_name="login_tokens")
    op.drop_index(op.f("ix_login_tokens_email"), table_name="login_tokens")
    op.drop_table("login_tokens")
