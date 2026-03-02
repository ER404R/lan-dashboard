import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import (
    flash,
    get_current_user,
    get_db,
    get_flashed_messages,
    require_admin,
)
from app.models import InviteToken, User

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


@router.get("/tokens", response_class=HTMLResponse)
async def tokens_page(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_admin(user, request)
    if redirect:
        return redirect

    tokens = db.query(InviteToken).order_by(InviteToken.created_at.desc()).all()

    return templates.TemplateResponse(
        "admin_tokens.html",
        {
            "request": request,
            "user": user,
            "tokens": tokens,
            "messages": get_flashed_messages(request),
        },
    )


@router.post("/tokens/generate")
async def generate_tokens(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_admin(user, request)
    if redirect:
        return redirect

    form = await request.form()
    try:
        count = min(int(form.get("count", 1)), 50)
    except (ValueError, TypeError):
        count = 1

    try:
        max_uses = int(form.get("max_uses", 1))
        if max_uses < 0:
            max_uses = 1
    except (ValueError, TypeError):
        max_uses = 1

    for _ in range(count):
        db.add(InviteToken(token=secrets.token_urlsafe(16), max_uses=max_uses))
    db.commit()

    uses_label = "unlimited" if max_uses == 0 else f"{max_uses}-use"
    flash(request, f"Generated {count} {uses_label} token(s).")
    return RedirectResponse("/admin/tokens", status_code=303)


@router.post("/tokens/{token_id}/revoke")
async def revoke_token(
    token_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_admin(user, request)
    if redirect:
        return redirect

    token = db.get(InviteToken, token_id)
    if not token:
        flash(request, "Token not found.")
        return RedirectResponse("/admin/tokens", status_code=303)

    token.revoked = not token.revoked
    db.commit()

    action = "revoked" if token.revoked else "restored"
    flash(request, f"Token {action}.")
    return RedirectResponse("/admin/tokens", status_code=303)


@router.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_admin(user, request)
    if redirect:
        return redirect

    users = db.query(User).order_by(User.created_at).all()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "messages": get_flashed_messages(request),
        },
    )
