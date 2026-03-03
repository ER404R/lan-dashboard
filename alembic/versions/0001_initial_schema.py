"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check which tables already exist (handles existing deployed DBs)
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(50), nullable=False),
            sa.Column("password_hash", sa.String(128), nullable=False),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("username"),
        )
        op.create_index("ix_users_username", "users", ["username"])

    if "games" not in existing:
        op.create_table(
            "games",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("steam_appid", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("steam_url", sa.String(512), nullable=False),
            sa.Column("thumbnail_url", sa.String(512), nullable=False),
            sa.Column("added_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("steam_appid"),
        )
        op.create_index("ix_games_steam_appid", "games", ["steam_appid"])

    if "scores" not in existing:
        op.create_table(
            "scores",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
            sa.Column("value", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "game_id"),
        )

    if "invite_tokens" not in existing:
        op.create_table(
            "invite_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token", sa.String(64), nullable=False),
            sa.Column("max_uses", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("use_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("token"),
        )
        op.create_index("ix_invite_tokens_token", "invite_tokens", ["token"])

    if "feature_requests" not in existing:
        op.create_table(
            "feature_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

    if "feature_comments" not in existing:
        op.create_table(
            "feature_comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("feature_request_id", sa.Integer(), sa.ForeignKey("feature_requests.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

    if "game_ownerships" not in existing:
        op.create_table(
            "game_ownerships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "game_id"),
        )


def downgrade() -> None:
    op.drop_table("game_ownerships")
    op.drop_table("feature_comments")
    op.drop_table("feature_requests")
    op.drop_table("invite_tokens")
    op.drop_table("scores")
    op.drop_table("games")
    op.drop_table("users")
