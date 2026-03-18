from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import settings
from app.csrf import get_csrf_token, verify_csrf_token
from app.dependencies import flash, get_current_user, get_db, get_flashed_messages
from app.limiter import limiter
from app.models import InviteToken, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "messages": get_flashed_messages(request),
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    db: Session = Depends(get_db),
    _csrf: None = Depends(verify_csrf_token),
):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")

    user = db.query(User).filter_by(username=username).first()
    if not user or not verify_password(password, user.password_hash):
        flash(request, "Invalid username or password.")
        return RedirectResponse("/login", status_code=303)

    # Phase 5 — session fixation prevention: clear old session before writing new identity
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "registration_enabled": settings.REGISTRATION_ENABLED,
            "messages": get_flashed_messages(request),
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    db: Session = Depends(get_db),
    _csrf: None = Depends(verify_csrf_token),
):
    if not settings.REGISTRATION_ENABLED:
        flash(request, "Registration is currently closed.")
        return RedirectResponse("/register", status_code=303)

    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    invite_token = form.get("invite_token", "").strip()

    if len(username) < 3:
        flash(request, "Username must be at least 3 characters.")
        return RedirectResponse("/register", status_code=303)

    # Phase 4a — raised minimum from 6 to 8
    if len(password) < 8:
        flash(request, "Password must be at least 8 characters.")
        return RedirectResponse("/register", status_code=303)

    # Check invite token
    token = db.query(InviteToken).filter_by(token=invite_token).first()
    if not token or not token.is_available:
        flash(request, "Invalid, revoked, or exhausted invite token.")
        return RedirectResponse("/register", status_code=303)

    # Check username uniqueness
    if db.query(User).filter_by(username=username).first():
        flash(request, "Username already taken.")
        return RedirectResponse("/register", status_code=303)

    # Create user (admin if using the admin invite token)
    is_admin = bool(settings.ADMIN_INVITE_TOKEN and invite_token == settings.ADMIN_INVITE_TOKEN)
    user = User(username=username, password_hash=hash_password(password), is_admin=is_admin)
    db.add(user)
    db.flush()

    # Increment token use count
    token.use_count += 1
    db.commit()

    flash(request, "Registration successful! Please log in.")
    return RedirectResponse("/login", status_code=303)


@router.post("/logout")
async def logout(
    request: Request,
    _csrf: None = Depends(verify_csrf_token),
):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
