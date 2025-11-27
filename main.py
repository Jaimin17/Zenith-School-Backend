from sched import scheduler

from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlmodel import Session
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
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

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
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
    )

app.include_router(api_router, prefix=settings.API_V1_STR)