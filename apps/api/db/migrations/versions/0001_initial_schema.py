"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-05-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eval_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("benchmark", sa.String(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benchmark", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("agent_version", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("task_count", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_eval_runs_created_at", "eval_runs", ["created_at"], postgresql_using="btree")

    op.create_table(
        "task_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eval_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Double(), nullable=True),
        sa.Column("stats", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_type", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["eval_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_task_runs_eval_run_id", "task_runs", ["eval_run_id"])

    op.create_table(
        "trace_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_trace_events_task_run_id_step",
        "trace_events",
        ["task_run_id", "step_index"],
    )


def downgrade() -> None:
    op.drop_table("trace_events")
    op.drop_table("task_runs")
    op.drop_table("eval_runs")
    op.drop_table("eval_tasks")
