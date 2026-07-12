from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.shared.db import engine, Base
from app.shared.storage import init_minio
from app.modules.notifications.handlers import register_notification_handlers

# Module routers
from app.modules.core.router import router as core_router
from app.modules.environmental.router import router as env_router
from app.modules.social.router import router as social_router
from app.modules.governance.router import router as gov_router
from app.modules.gamification.router import router as game_router
from app.modules.notifications.router import router as notif_router
from app.modules.scoring_reporting.router import router as score_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_minio()
    register_notification_handlers()
    yield
    # Shutdown - nothing to clean up


app = FastAPI(
    title="EcoSphere API",
    description="ESG Management Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(core_router, prefix="/core", tags=["Core"])
app.include_router(env_router, prefix="/environmental", tags=["Environmental"])
app.include_router(social_router, prefix="/social", tags=["Social"])
app.include_router(gov_router, prefix="/governance", tags=["Governance"])
app.include_router(game_router, prefix="/gamification", tags=["Gamification"])
app.include_router(notif_router, prefix="/notifications", tags=["Notifications"])
app.include_router(score_router, prefix="/scoring", tags=["Scoring & Reporting"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "ecosphere-api"}


@app.get("/", tags=["Health"])
async def root():
    return {"message": "EcoSphere API is running", "docs": "/docs"}
