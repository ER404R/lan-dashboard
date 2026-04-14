"""widen password_hash column to Text

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "password_hash",
                existing_type=sa.String(128),
                type_=sa.Text(),
                existing_nullable=False,
            )
    else:
        op.alter_column(
            "users",
            "password_hash",
            existing_type=sa.String(128),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "password_hash",
                existing_type=sa.Text(),
                type_=sa.String(128),
                existing_nullable=False,
            )
    else:
        op.alter_column(
            "users",
            "password_hash",
            existing_type=sa.Text(),
            type_=sa.String(128),
            existing_nullable=False,
        )
