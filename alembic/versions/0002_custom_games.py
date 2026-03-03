"""make steam fields nullable for custom games

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.alter_column("steam_appid", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("steam_url", existing_type=sa.String(512), nullable=True)
        batch_op.alter_column("thumbnail_url", existing_type=sa.String(512), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.alter_column("steam_appid", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("steam_url", existing_type=sa.String(512), nullable=False)
        batch_op.alter_column("thumbnail_url", existing_type=sa.String(512), nullable=False)
