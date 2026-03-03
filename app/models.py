from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    scores: Mapped[list["Score"]] = relationship(back_populates="user")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    steam_appid: Mapped[int | None] = mapped_column(unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    steam_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    scores: Mapped[list["Score"]] = relationship(back_populates="game")
    added_by: Mapped["User"] = relationship()


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    value: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="scores")
    game: Mapped["Game"] = relationship(back_populates="scores")

    __table_args__ = (UniqueConstraint("user_id", "game_id"),)


class InviteToken(Base):
    __tablename__ = "invite_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    max_uses: Mapped[int] = mapped_column(default=1)  # 0 = unlimited
    use_count: Mapped[int] = mapped_column(default=0)
    revoked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    @property
    def is_available(self) -> bool:
        if self.revoked:
            return False
        if self.max_uses == 0:
            return True
        return self.use_count < self.max_uses

    @property
    def status_label(self) -> str:
        if self.revoked:
            return "Revoked"
        if self.max_uses != 0 and self.use_count >= self.max_uses:
            return "Exhausted"
        return "Available"


class FeatureRequest(Base):
    __tablename__ = "feature_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship()
    comments: Mapped[list["FeatureComment"]] = relationship(
        back_populates="feature_request", cascade="all, delete-orphan"
    )


class FeatureComment(Base):
    __tablename__ = "feature_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_request_id: Mapped[int] = mapped_column(ForeignKey("feature_requests.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship()
    feature_request: Mapped["FeatureRequest"] = relationship(back_populates="comments")


class GameOwnership(Base):
    __tablename__ = "game_ownerships"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    status: Mapped[str] = mapped_column(String(10))  # "owned" or "want"
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship()
    game: Mapped["Game"] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "game_id"),)
