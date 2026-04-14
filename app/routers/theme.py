from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.csrf import verify_csrf_token
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/theme")


@router.post("/toggle")
async def toggle_theme(
    request: Request,
    _csrf: None = Depends(verify_csrf_token),
    user: User | None = Depends(get_current_user),
):
    current = request.session.get("theme", "dark")
    request.session["theme"] = "light" if current == "dark" else "dark"

    # Safe redirect back via Referer, falling back to "/"
    referer = request.headers.get("referer", "")
    base = str(request.base_url).rstrip("/")
    if referer.startswith(base):
        redirect_path = referer[len(base):] or "/"
    else:
        redirect_path = "/"

    return RedirectResponse(redirect_path, status_code=303)
