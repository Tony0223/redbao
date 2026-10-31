"""Create quiz results table.

Revision ID: 20260729_0001
Revises:
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quiz_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic_id", sa.String(length=50), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_quiz_results_created_at",
        "quiz_results",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_quiz_results_topic_created",
        "quiz_results",
        ["topic_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_quiz_results_topic_created", table_name="quiz_results")
    op.drop_index("ix_quiz_results_created_at", table_name="quiz_results")
    op.drop_table("quiz_results")
