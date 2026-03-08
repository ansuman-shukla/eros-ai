"""Companion AI — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.mongodb import init_db, close_db
from app.db.redis_client import init_redis, close_redis
from app.utils.errors import (
    NotFoundError,
    UnauthorizedError,
    InsufficientCoinsError,
    SessionNotActiveError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle hooks."""
    await init_db()
    await init_redis()
    yield
    await close_redis()
    await close_db()


app = FastAPI(
    title="Eros AI",
    description="A deeply personal AI companion with persistent memory and evolving personality.",
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS (allow frontend to call backend) ──────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global exception handlers ──────────────────────────────────────────────


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(InsufficientCoinsError)
async def insufficient_coins_handler(request: Request, exc: InsufficientCoinsError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(SessionNotActiveError)
async def session_not_active_handler(request: Request, exc: SessionNotActiveError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ─── Health check ────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Router registration ────────────────────────────────────────────────────

from app.api.v1 import auth, session, memory, chat, coins, voice, dashboard, persona

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(session.router, prefix="/api/v1/session", tags=["session"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(chat.router, tags=["chat"])
app.include_router(coins.router, prefix="/api/v1/coins", tags=["coins"])
app.include_router(voice.router, prefix="/api/v1/voice", tags=["voice"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(persona.router, prefix="/api/v1/persona", tags=["persona"])
