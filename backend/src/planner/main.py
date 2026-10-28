"""FastAPI application. Run with: ``uv run uvicorn planner.main:app --reload``"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from planner.api import auth, goals, notifications
from planner.config import get_settings
from planner.db.session import get_engine, new_session
from planner.llm.gateway import ModelOutputError, ModelUnavailableError, get_gateway
from planner.services.checkins import Scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()  # creates tables on first start
    scheduler = None
    if get_settings().scheduler_enabled:
        scheduler = Scheduler(get_gateway(), new_session)
        scheduler.start()
    yield
    if scheduler:
        scheduler.stop()


app = FastAPI(title="my_planner API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(goals.router)
app.include_router(notifications.router)


@app.exception_handler(ModelUnavailableError)
async def _model_unavailable(_req: Request, exc: ModelUnavailableError):
    return JSONResponse(status_code=503, content={"detail": "model server unavailable", "error": str(exc)})


@app.exception_handler(ModelOutputError)
async def _model_output(_req: Request, exc: ModelOutputError):
    return JSONResponse(status_code=502, content={"detail": "model returned invalid output", "error": str(exc)})


@app.get("/health")
def health():
    return {"ok": True}
