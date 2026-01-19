from contextlib import asynccontextmanager
from sched import scheduler

from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlmodel import Session
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from starlette.staticfiles import StaticFiles

from core.config import settings
from core.database import init_db
from core.security import delete_old_blacklisted_tokens
from routers.main import api_router
import os

if os.getenv("RUN_MAIN") == "true":
    scheduler.start()


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"

init_db(Session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events - runs on startup and shutdown
    """
    # Startup: Create upload directories if they don't exist
    print("🚀 Starting FastAPI application...")

    # Create upload directories
    settings.UPLOAD_DIR_DP.mkdir(parents=True, exist_ok=True)
    settings.UPLOAD_DIR_PDF.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for different user types
    (settings.UPLOAD_DIR_DP / "teachers").mkdir(exist_ok=True)
    (settings.UPLOAD_DIR_DP / "students").mkdir(exist_ok=True)
    (settings.UPLOAD_DIR_DP / "parents").mkdir(exist_ok=True)

    print(f"✓ Upload directories created:")
    print(f"  - Images: {settings.UPLOAD_DIR_DP.absolute()}")
    print(f"  - PDFs: {settings.UPLOAD_DIR_PDF.absolute()}")

    yield

    # Shutdown
    print("👋 Shutting down FastAPI application...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_blacklisted_tokens, "cron", day_of_week="mon", hour=1)
scheduler.start()

if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

if settings.UPLOAD_DIR_DP.exists():
    app.mount(
        "/uploads/images",
        StaticFiles(directory=str(settings.UPLOAD_DIR_DP)),
        name="images"
    )
    print(f"✓ Static files mounted at /uploads/images")
    print(f"  Example: http://localhost:8000/uploads/images/teachers/filename.jpg")

# Mount PDFs directory
if settings.UPLOAD_DIR_PDF.exists():
    app.mount(
        "/uploads/pdfs",
        StaticFiles(directory=str(settings.UPLOAD_DIR_PDF)),
        name="pdfs"
    )
    print(f"✓ Static files mounted at /uploads/pdfs")

app.include_router(api_router, prefix=settings.API_V1_STR)