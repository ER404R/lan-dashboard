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
    require_login,
)
from app.models import FeatureComment, FeatureRequest, User

router = APIRouter(prefix="/features")
templates = Jinja2Templates(directory="app/templates")

MAX_OPEN_REQUESTS_PER_USER = 3


@router.get("", response_class=HTMLResponse)
async def list_features(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_login(user, request)
    if redirect:
        return redirect

    features = (
        db.query(FeatureRequest)
        .order_by(FeatureRequest.resolved, FeatureRequest.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "features.html",
        {
            "request": request,
            "user": user,
            "features": features,
            "messages": get_flashed_messages(request),
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_feature_form(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_login(user, request)
    if redirect:
        return redirect

    open_count = db.query(FeatureRequest).filter_by(user_id=user.id, resolved=False).count()
    can_create = open_count < MAX_OPEN_REQUESTS_PER_USER

    return templates.TemplateResponse(
        "feature_new.html",
        {
            "request": request,
            "user": user,
            "can_create": can_create,
            "open_count": open_count,
            "max_requests": MAX_OPEN_REQUESTS_PER_USER,
            "messages": get_flashed_messages(request),
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_feature(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_login(user, request)
    if redirect:
        return redirect

    open_count = db.query(FeatureRequest).filter_by(user_id=user.id, resolved=False).count()
    if open_count >= MAX_OPEN_REQUESTS_PER_USER:
        flash(request, f"You can only have {MAX_OPEN_REQUESTS_PER_USER} open requests at a time.")
        return RedirectResponse("/features", status_code=303)

    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()

    if not title or len(title) > 200:
        flash(request, "Title is required (max 200 characters).")
        return RedirectResponse("/features/new", status_code=303)

    if not description:
        flash(request, "Description is required.")
        return RedirectResponse("/features/new", status_code=303)

    feature = FeatureRequest(title=title, description=description, user_id=user.id)
    db.add(feature)
    db.commit()

    flash(request, "Feature request created!")
    return RedirectResponse("/features", status_code=303)


@router.get("/{feature_id}", response_class=HTMLResponse)
async def feature_detail(
    feature_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_login(user, request)
    if redirect:
        return redirect

    feature = db.get(FeatureRequest, feature_id)
    if not feature:
        flash(request, "Feature request not found.")
        return RedirectResponse("/features", status_code=303)

    comments = (
        db.query(FeatureComment)
        .filter_by(feature_request_id=feature_id)
        .order_by(FeatureComment.created_at)
        .all()
    )

    return templates.TemplateResponse(
        "feature_detail.html",
        {
            "request": request,
            "user": user,
            "feature": feature,
            "comments": comments,
            "messages": get_flashed_messages(request),
        },
    )


@router.post("/{feature_id}/comment")
async def add_comment(
    feature_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_login(user, request)
    if redirect:
        return redirect

    feature = db.get(FeatureRequest, feature_id)
    if not feature:
        flash(request, "Feature request not found.")
        return RedirectResponse("/features", status_code=303)

    form = await request.form()
    content = form.get("content", "").strip()

    if not content:
        flash(request, "Comment cannot be empty.")
        return RedirectResponse(f"/features/{feature_id}", status_code=303)

    comment = FeatureComment(
        feature_request_id=feature_id, user_id=user.id, content=content
    )
    db.add(comment)
    db.commit()

    return RedirectResponse(f"/features/{feature_id}", status_code=303)


@router.post("/{feature_id}/resolve")
async def resolve_feature(
    feature_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_admin(user, request)
    if redirect:
        return redirect

    feature = db.get(FeatureRequest, feature_id)
    if not feature:
        flash(request, "Feature request not found.")
        return RedirectResponse("/features", status_code=303)

    feature.resolved = not feature.resolved
    db.commit()

    status = "resolved" if feature.resolved else "reopened"
    flash(request, f"Feature request {status}.")
    return RedirectResponse(f"/features/{feature_id}", status_code=303)


@router.post("/{feature_id}/delete")
async def delete_feature(
    feature_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redirect = require_admin(user, request)
    if redirect:
        return redirect

    feature = db.get(FeatureRequest, feature_id)
    if not feature:
        flash(request, "Feature request not found.")
        return RedirectResponse("/features", status_code=303)

    db.delete(feature)
    db.commit()

    flash(request, "Feature request deleted.")
    return RedirectResponse("/features", status_code=303)
