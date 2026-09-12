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

    # Seed demo data
    from app.seed import seed_database
    await seed_database()

    # Start background scheduler (optional, can be disabled)
    try:
        from app.workers.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start skipped: {e}")

    yield

    # Shutdown
    try:
        from app.workers.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
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
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
