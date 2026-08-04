from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import create_cockpit_router, create_legacy_router
from .api.legacy_router import (
    build_demo_trip,
    demo_trip,
    events,
    report,
    simulation,
)
from .cockpit.errors import CommandRejected
from .cockpit.service import CockpitService
from .config import RuntimeSettings, load_settings
from .data import load_mock_frames

__all__ = [
    "app",
    "create_app",
    "build_demo_trip",
    "demo_trip",
    "events",
    "report",
    "simulation",
]

LOCAL_UI_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_mock_frames()
    yield


def create_app(
    authority: CockpitService | None = None,
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    runtime_settings = settings or load_settings()
    cockpit_authority = authority or CockpitService()

    api = FastAPI(
        title="Supersonic 智能座舱 HMI API",
        version="0.2.0",
        lifespan=lifespan,
    )
    api.state.cockpit_authority = cockpit_authority
    api.state.settings = runtime_settings

    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_UI_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.exception_handler(CommandRejected)
    async def command_rejected(_: Request, exc: CommandRejected) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @api.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": runtime_settings.app_mode.value}

    api.include_router(create_legacy_router())
    api.include_router(create_cockpit_router(cockpit_authority, runtime_settings))
    return api


app = create_app()
