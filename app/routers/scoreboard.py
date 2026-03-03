from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func as sa_func
from sqlalchemy.orm import Session

from app.dependencies import flash, get_current_user, get_db, get_flashed_messages
from app.models import Game, GameOwnership, Score, User
from app.steam import search_steam_games

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def scoreboard(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
    filter: str = "",
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Subqueries to avoid cross-product between Score and GameOwnership
    score_sub = (
        db.query(
            Score.game_id,
            sa_func.avg(Score.value).label("avg_score"),
            sa_func.count(Score.id).label("num_ratings"),
        )
        .group_by(Score.game_id)
        .subquery()
    )

    ownership_sub = (
        db.query(
            GameOwnership.game_id,
            sa_func.count(case((GameOwnership.status == "owned", GameOwnership.id))).label("owner_count"),
            sa_func.count(case((GameOwnership.status == "want", GameOwnership.id))).label("want_count"),
        )
        .group_by(GameOwnership.game_id)
        .subquery()
    )

    query = (
        db.query(
            Game,
            sa_func.coalesce(score_sub.c.avg_score, 0).label("avg_score"),
            sa_func.coalesce(score_sub.c.num_ratings, 0).label("num_ratings"),
            sa_func.coalesce(ownership_sub.c.owner_count, 0).label("owner_count"),
            sa_func.coalesce(ownership_sub.c.want_count, 0).label("want_count"),
        )
        .outerjoin(score_sub, Game.id == score_sub.c.game_id)
        .outerjoin(ownership_sub, Game.id == ownership_sub.c.game_id)
        .order_by(score_sub.c.avg_score.desc().nulls_last())
    )

    if filter == "new":
        query = query.filter(sa_func.coalesce(ownership_sub.c.owner_count, 0) < 2)

    games_with_scores = query.all()

    # Get current user's scores and ownership
    user_scores = {s.game_id: s.value for s in db.query(Score).filter_by(user_id=user.id).all()}
    user_ownership = {
        o.game_id: o.status
        for o in db.query(GameOwnership).filter_by(user_id=user.id).all()
    }

    return templates.TemplateResponse(
        "scoreboard.html",
        {
            "request": request,
            "user": user,
            "games_with_scores": games_with_scores,
            "user_scores": user_scores,
            "user_ownership": user_ownership,
            "current_filter": filter,
            "messages": get_flashed_messages(request),
        },
    )


@router.get("/games/search-steam", response_class=HTMLResponse)
async def search_steam(request: Request, q: str = "", user: User | None = Depends(get_current_user)):
    if not user:
        return HTMLResponse("")

    if len(q.strip()) < 2:
        return HTMLResponse("")

    try:
        results = await search_steam_games(q.strip())
    except Exception:
        return HTMLResponse("<p>Failed to search Steam. Please try again.</p>")

    return templates.TemplateResponse(
        "_search_results.html",
        {"request": request, "results": results},
    )


@router.post("/games/add")
async def add_game(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    form = await request.form()
    steam_appid = int(form.get("steam_appid", 0))
    name = form.get("name", "").strip()
    thumbnail_url = form.get("thumbnail_url", "")
    steam_url = form.get("steam_url", "")

    if not steam_appid or not name:
        flash(request, "Invalid game data.")
        return RedirectResponse("/", status_code=303)

    # Check if game already exists
    existing = db.query(Game).filter_by(steam_appid=steam_appid).first()
    if existing:
        flash(request, f"'{name}' is already on the scoreboard.")
        return RedirectResponse("/", status_code=303)

    game = Game(
        steam_appid=steam_appid,
        name=name,
        steam_url=steam_url,
        thumbnail_url=thumbnail_url,
        added_by_id=user.id,
    )
    db.add(game)
    db.commit()

    flash(request, f"'{name}' added to the scoreboard!")
    return RedirectResponse("/", status_code=303)


@router.post("/games/add-custom")
async def add_custom_game(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    form = await request.form()
    name = form.get("name", "").strip()
    thumbnail_url = form.get("thumbnail_url", "").strip() or None

    if not name:
        flash(request, "Game name is required.")
        return RedirectResponse("/", status_code=303)

    # Check if a custom game with the same name already exists
    existing = db.query(Game).filter(Game.name == name, Game.steam_appid.is_(None)).first()
    if existing:
        flash(request, f"'{name}' is already on the scoreboard.")
        return RedirectResponse("/", status_code=303)

    game = Game(
        name=name,
        thumbnail_url=thumbnail_url,
        added_by_id=user.id,
    )
    db.add(game)
    db.commit()

    flash(request, f"'{name}' added to the scoreboard!")
    return RedirectResponse("/", status_code=303)


@router.post("/games/{game_id}/rate")
async def rate_game(
    game_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    form = await request.form()
    try:
        value = int(form.get("value", -1))
    except (ValueError, TypeError):
        flash(request, "Invalid rating.")
        return RedirectResponse("/", status_code=303)

    if value < 0 or value > 10:
        flash(request, "Rating must be between 0 and 10.")
        return RedirectResponse("/", status_code=303)

    # Check game exists
    game = db.get(Game, game_id)
    if not game:
        flash(request, "Game not found.")
        return RedirectResponse("/", status_code=303)

    # Upsert score
    existing = db.query(Score).filter_by(user_id=user.id, game_id=game_id).first()
    if existing:
        existing.value = value
    else:
        db.add(Score(user_id=user.id, game_id=game_id, value=value))
    db.commit()

    return RedirectResponse("/", status_code=303)


@router.post("/games/{game_id}/ownership")
async def set_ownership(
    game_id: int,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    game = db.get(Game, game_id)
    if not game:
        flash(request, "Game not found.")
        return RedirectResponse("/", status_code=303)

    form = await request.form()
    status = form.get("status", "").strip()

    existing = db.query(GameOwnership).filter_by(user_id=user.id, game_id=game_id).first()

    if status in ("owned", "want"):
        if existing:
            existing.status = status
        else:
            db.add(GameOwnership(user_id=user.id, game_id=game_id, status=status))
    else:
        # "none" or empty — remove ownership record
        if existing:
            db.delete(existing)

    db.commit()
    return RedirectResponse("/", status_code=303)
