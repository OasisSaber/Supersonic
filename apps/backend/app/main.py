from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .adapters.postgres.database import create_database_engine, create_session_factory
from .adapters.postgres.readiness import SqlAlchemyPlatformReadiness
from .adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from .adapters.security import PwdlibPasswordHasher
from .api import create_cockpit_router, create_legacy_router
from .api.legacy_router import (
    build_demo_trip,
    demo_trip,
    events,
    report,
    simulation,
)
from .api.platform_session_router import (
    PlatformSessionService,
    PlatformUnavailable,
    create_platform_session_router,
)
from .cockpit.errors import CommandRejected
from .cockpit.service import CockpitService
from .config import RuntimeSettings, load_settings
from .data import load_mock_frames
from .platform.sessions import SessionService
from .platform.throttle import LoginThrottle

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


class _UnavailablePlatformSessionService:
    async def login(self, username: str, password: str, remote_client_key: str) -> None:
        raise PlatformUnavailable

    async def logout(self, raw_secret: str) -> None:
        raise PlatformUnavailable

    async def resolve(self, raw_secret: str) -> None:
        raise PlatformUnavailable


def create_app(
    authority: CockpitService | None = None,
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    runtime_settings = settings or load_settings()
    cockpit_authority = authority or CockpitService()
    database_engine = None
    platform_service: PlatformSessionService = _UnavailablePlatformSessionService()
    if runtime_settings.database_url is not None:
        database_engine = create_database_engine(runtime_settings.database_url)
        session_factory = create_session_factory(database_engine)
        readiness = SqlAlchemyPlatformReadiness(
            runtime_settings.database_url,
            engine=database_engine,
        )
        platform_service = SessionService(
            readiness=readiness,
            uow_factory=lambda: SqlAlchemyPlatformUnitOfWork(session_factory),
            password_hasher=PwdlibPasswordHasher(),
            throttle=LoginThrottle(),
            session_ttl=timedelta(seconds=runtime_settings.platform_session_ttl_seconds),
            clock=lambda: datetime.now(UTC),
            uuid_factory=lambda: str(uuid4()),
        )

    @asynccontextmanager
    async def app_lifespan(_: FastAPI):
        load_mock_frames()
        try:
            yield
        finally:
            if database_engine is not None:
                await database_engine.dispose()

    api = FastAPI(
        title="Supersonic 智能座舱 HMI API",
        version="0.2.0",
        lifespan=app_lifespan,
    )
    api.state.cockpit_authority = cockpit_authority
    api.state.settings = runtime_settings

    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys((*LOCAL_UI_ORIGINS, runtime_settings.platform_ui_origin))),
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
    api.include_router(create_platform_session_router(platform_service, runtime_settings))
    return api


app = create_app()
