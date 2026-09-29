from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import logger

# API Routers
from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.resume import router as resume_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.applications import router as applications_router
from app.api.v1.sources import router as sources_router
from app.api.v1.automation import router as automation_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.audit import router as audit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")

    # Initialize database tables
    await init_db()
    logger.info("✅ Database initialized")

    # Seed automated job source configs (enable/disable gating)
    from app.core.database import AsyncSessionLocal
    from app.services.source_config_service import sync_source_configs
    async with AsyncSessionLocal() as db:
        await sync_source_configs(db)
    logger.info("✅ Job source configs synchronized")

    # Seed demo data only if explicitly enabled
    from app.seed import seed_database
    await seed_database()

    yield

    logger.info("🛑 Application shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered job application automation with ethical human-in-the-loop workflows.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=prefix)
app.include_router(profile_router, prefix=prefix)
app.include_router(resume_router, prefix=prefix)
app.include_router(jobs_router, prefix=prefix)
app.include_router(applications_router, prefix=prefix)
app.include_router(sources_router, prefix=prefix)
app.include_router(automation_router, prefix=prefix)
app.include_router(notifications_router, prefix=prefix)
app.include_router(analytics_router, prefix=prefix)
app.include_router(audit_router, prefix=prefix)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "dry_run": settings.DRY_RUN,
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "database": "connected",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready")
async def ready():
    return {
        "status": "ready",
        "database": "connected",
        "ai_provider": settings.AI_PROVIDER,
        "ai_configured": settings.OPENAI_API_KEY != "",
    }