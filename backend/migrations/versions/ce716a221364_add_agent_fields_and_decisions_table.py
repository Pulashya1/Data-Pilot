"""add agent fields to sessions and decisions table

Revision ID: ce716a221364
Revises: 1f5b28ea04d6
Create Date: 2026-09-16 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ce716a221364"
down_revision: str | None = "1f5b28ea04d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "problem_type",
            sa.Enum(
                "REGRESSION",
                "BINARY_CLASSIFICATION",
                "MULTICLASS_CLASSIFICATION",
                "CLUSTERING",
                "TIME_SERIES",
                name="problemtype",
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("sessions", sa.Column("target_column", sa.String(length=255), nullable=True))
    op.add_column(
        "sessions",
        sa.Column(
            "agent_status",
            sa.Enum(
                "NOT_STARTED", "RUNNING", "DONE", "ERROR", name="agentstatus", native_enum=False
            ),
            nullable=False,
            server_default="NOT_STARTED",
        ),
    )
    op.add_column("sessions", sa.Column("agent_error_message", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("plan_steps", sa.JSON(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("plan_step_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "sessions",
        sa.Column("llm_calls_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "sessions",
        sa.Column("llm_tokens_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("sessions", sa.Column("llm_models_used", sa.JSON(), nullable=True))

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("TARGET_CONFIRMATION", "PLAN_APPROVAL", name="decisionkind", native_enum=False),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("recommended_option", sa.String(length=255), nullable=True),
        sa.Column("selected_option", sa.String(length=255), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("auto_decided", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decisions_session_id"), "decisions", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_decisions_session_id"), table_name="decisions")
    op.drop_table("decisions")

    op.drop_column("sessions", "llm_models_used")
    op.drop_column("sessions", "llm_tokens_used")
    op.drop_column("sessions", "llm_calls_used")
    op.drop_column("sessions", "plan_step_index")
    op.drop_column("sessions", "plan_steps")
    op.drop_column("sessions", "agent_error_message")
    op.drop_column("sessions", "agent_status")
    op.drop_column("sessions", "target_column")
    op.drop_column("sessions", "problem_type")
