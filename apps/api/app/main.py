import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.v1.router import api_router
from app.database import SessionLocal
from app.api.v1.applications import seed_sample_institutions_if_empty
from app.services.routing_health import automated_expiry_sweep_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_sample_institutions_if_empty(db)
    finally:
        db.close()

    sweep_task = None
    if settings.ENABLE_AUTOMATED_EXPIRY_SWEEPS:
        sweep_task = asyncio.create_task(
            automated_expiry_sweep_loop(settings.ROUTE_EXPIRY_SWEEP_INTERVAL_SECONDS, SessionLocal)
        )
    try:
        yield
    finally:
        if sweep_task is not None:
            sweep_task.cancel()
            try:
                await sweep_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for Global University Application & Admissions Intelligence Platform",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "platform": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR
    }
