from collections.abc import Generator

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def flash(request: Request, message: str) -> None:
    request.session.setdefault("_flashes", []).append(message)


def get_flashed_messages(request: Request) -> list[str]:
    return request.session.pop("_flashes", [])


def require_login(user: User | None, request: Request) -> RedirectResponse | None:
    if not user:
        flash(request, "Please log in.")
        return RedirectResponse("/login", status_code=303)
    return None


def require_admin(user: User | None, request: Request) -> RedirectResponse | None:
    redirect = require_login(user, request)
    if redirect:
        return redirect
    if not user.is_admin:
        flash(request, "Admin access required.")
        return RedirectResponse("/", status_code=303)
    return None
