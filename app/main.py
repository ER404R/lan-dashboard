from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import SessionLocal, create_tables
from app.limiter import limiter
from app.models import InviteToken
from app.routers import admin, auth_routes, feature_requests, scoreboard

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        # Seed regular invite tokens
        if settings.SEED_INVITE_TOKENS:
            for token_str in settings.SEED_INVITE_TOKENS.split(","):
                token_str = token_str.strip()
                if token_str and not db.query(InviteToken).filter_by(token=token_str).first():
                    db.add(InviteToken(token=token_str))
        # Seed admin invite token
        if settings.ADMIN_INVITE_TOKEN:
            token_str = settings.ADMIN_INVITE_TOKEN.strip()
            if token_str and not db.query(InviteToken).filter_by(token=token_str).first():
                db.add(InviteToken(token=token_str))
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="LAN Dashboard", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth_routes.router)
app.include_router(scoreboard.router)
app.include_router(admin.router)
app.include_router(feature_requests.router)
