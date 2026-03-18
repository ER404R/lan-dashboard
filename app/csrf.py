"""CSRF protection using itsdangerous signed tokens stored in the session."""

import hmac
import secrets

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

# Token lifetime: 1 hour
_MAX_AGE = 3600


def get_csrf_token(request: Request) -> str:
    """Return a signed CSRF token for the current session.

    Generates a random raw token on first call and persists it in the session.
    Each call returns a freshly-signed representation of the same raw token so
    that multiple forms on one page all share a single session value.
    """
    if "_csrf_token" not in request.session:
        request.session["_csrf_token"] = secrets.token_hex(32)

    s = URLSafeTimedSerializer(settings.SECRET_KEY, salt="csrf")
    return s.dumps(request.session["_csrf_token"])


async def verify_csrf_token(request: Request) -> None:
    """FastAPI dependency — raises HTTP 403 if the submitted CSRF token is
    absent, expired, or does not match the session token."""

    form = await request.form()
    submitted = str(form.get("csrf_token", ""))
    session_token = request.session.get("_csrf_token")

    if not submitted or not session_token:
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")

    s = URLSafeTimedSerializer(settings.SECRET_KEY, salt="csrf")
    try:
        unsigned_value = s.loads(submitted, max_age=_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=403, detail="CSRF token expired — refresh the page and try again")
    except BadSignature:
        raise HTTPException(status_code=403, detail="CSRF token invalid")

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(str(unsigned_value), str(session_token)):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")
