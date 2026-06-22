"""FastAPI application entrypoint.

Wires up routes, CORS, security headers, and (in dev) table creation on startup.
In production, schema is managed by Alembic and `init_db` is skipped.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, liens
from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "development":
        await init_db()
    yield


app = FastAPI(
    title="Lien API",
    version="0.1.0",
    description="Normalized mechanic's lien records across jurisdictions.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["X-API-Key", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(health.router)
app.include_router(liens.router)
