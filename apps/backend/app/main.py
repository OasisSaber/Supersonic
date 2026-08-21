from __future__ import annotations

from collections.abc import Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Never
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp

from .adapters.postgres.audit_sink import PostgresAuditSink
from .adapters.postgres.database import create_database_engine, create_session_factory
from .adapters.postgres.readiness import SqlAlchemyPlatformReadiness
from .adapters.postgres.unit_of_work import SqlAlchemyPlatformUnitOfWork
from .adapters.security import PwdlibPasswordHasher
from .api import (
    create_cockpit_router,
    create_legacy_router,
    create_platform_admin_router,
)
from .api.cockpit_router import PlatformCommandWire
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
from .contracts.v1 import CommandEnvelopeV1, EndpointId
from .data import load_mock_frames
from .platform.admin import UserAdminService
from .platform.audit_query import AuditQueryService
from .platform.command_gateway import GatewayResult, PlatformCommandGateway
from .platform.errors import AuditUnavailable, AuthenticationRequired, RoleForbidden
from .platform.sessions import SessionIdentity, SessionService
from .platform.throttle import LoginThrottle
from .platform.websocket_registry import WebSocketSessionRegistry

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


class StrictCORSMiddleware(CORSMiddleware):
    """Keep the configured CORS request-header contract exact."""

    def __init__(
        self,
        app: ASGIApp,
        allow_origins: Sequence[str] = (),
        allow_methods: Sequence[str] = ("GET",),
        allow_headers: Sequence[str] = (),
        allow_credentials: bool = False,
        allow_origin_regex: str | None = None,
        allow_private_network: bool = False,
        expose_headers: Sequence[str] = (),
        max_age: int = 600,
    ) -> None:
        super().__init__(
            app=app,
            allow_origins=allow_origins,
            allow_methods=allow_methods,
            allow_headers=allow_headers,
            allow_credentials=allow_credentials,
            allow_origin_regex=allow_origin_regex,
            allow_private_network=allow_private_network,
            expose_headers=expose_headers,
            max_age=max_age,
        )
        # Starlette adds browser-safelisted headers. This platform contract permits only
        # the supplied preflight request headers, so restore that exact set.
        self.allow_headers = [header.lower() for header in allow_headers]
        if self.allow_headers and not self.allow_all_headers:
            self.preflight_headers["Access-Control-Allow-Headers"] = ", ".join(allow_headers)
        elif not self.allow_all_headers:
            self.preflight_headers.pop("Access-Control-Allow-Headers", None)


class _UnavailablePlatformSessionService:
    async def login(self, username: str, password: str, remote_client_key: str) -> None:
        raise PlatformUnavailable

    async def logout(self, raw_secret: str) -> None:
        raise PlatformUnavailable

    async def resolve(self, raw_secret: str) -> None:
        raise PlatformUnavailable


class _UnavailablePlatformAdminService:
    async def list_users(self, *_: object, **__: object) -> Never:
        raise PlatformUnavailable

    async def list_sessions(self, *_: object, **__: object) -> Never:
        raise PlatformUnavailable

    async def change_role(self, *_: object, **__: object) -> Never:
        raise PlatformUnavailable

    async def set_disabled(self, *_: object, **__: object) -> Never:
        raise PlatformUnavailable

    async def revoke_session(self, *_: object, **__: object) -> Never:
        raise PlatformUnavailable


class _UnavailablePlatformAuditService:
    async def list_for_role(self, *_: object, **__: object) -> Never:
        raise PlatformUnavailable


def create_app(
    authority: CockpitService | None = None,
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    runtime_settings = settings or load_settings()
    cockpit_authority = authority or CockpitService()
    database_engine = None
    platform_service: PlatformSessionService = _UnavailablePlatformSessionService()
    platform_admin = _UnavailablePlatformAdminService()
    platform_audit = _UnavailablePlatformAuditService()
    if runtime_settings.database_url is not None:
        database_engine = create_database_engine(runtime_settings.database_url)
        session_factory = create_session_factory(database_engine)
        readiness = SqlAlchemyPlatformReadiness(
            runtime_settings.database_url,
            engine=database_engine,
        )
        ws_registry = WebSocketSessionRegistry()

        def uow_factory() -> SqlAlchemyPlatformUnitOfWork:
            return SqlAlchemyPlatformUnitOfWork(session_factory)

        platform_service = SessionService(
            readiness=readiness,
            uow_factory=uow_factory,
            password_hasher=PwdlibPasswordHasher(),
            throttle=LoginThrottle(),
            session_ttl=timedelta(seconds=runtime_settings.platform_session_ttl_seconds),
            clock=lambda: datetime.now(UTC),
            uuid_factory=lambda: str(uuid4()),
            on_revoke=ws_registry.close_all,
        )
        platform_admin = UserAdminService(
            readiness=readiness,
            uow_factory=uow_factory,
            clock=lambda: datetime.now(UTC),
            uuid_factory=lambda: str(uuid4()),
            on_revoke=ws_registry.close_all,
        )
        platform_audit = AuditQueryService(
            readiness=readiness,
            uow_factory=uow_factory,
        )
        audit_sink = PostgresAuditSink(
            readiness=readiness,
            uow_factory=uow_factory,
        )
        platform_gateway = PlatformCommandGateway(
            authority=cockpit_authority,
            audit=audit_sink,
        )

        class _PlatformCommandWire:
            def cookie_name(self) -> str:
                return runtime_settings.platform_cookie.name

            async def resolve(self, raw_secret: str) -> SessionIdentity:
                return await platform_service.resolve(raw_secret)

            async def apply(
                self,
                identity: SessionIdentity,
                command: CommandEnvelopeV1,
                *,
                server_endpoint: EndpointId,
            ) -> GatewayResult:
                return await platform_gateway.apply_command(
                    identity.principal,
                    command,
                    server_endpoint=server_endpoint,
                )

        platform_wire: PlatformCommandWire | None = _PlatformCommandWire()
    else:
        ws_registry = None
        platform_wire = None

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
        StrictCORSMiddleware,
        allow_origins=list(dict.fromkeys((*LOCAL_UI_ORIGINS, runtime_settings.platform_ui_origin))),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @api.exception_handler(CommandRejected)
    async def command_rejected(_: Request, exc: CommandRejected) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @api.exception_handler(AuthenticationRequired)
    async def authentication_required(_: Request, exc: AuthenticationRequired) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @api.exception_handler(RoleForbidden)
    async def role_forbidden(_: Request, exc: RoleForbidden) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @api.exception_handler(AuditUnavailable)
    async def audit_unavailable(_: Request, exc: AuditUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "audit_unavailable",
                    "message": "The audit boundary is unavailable.",
                }
            },
        )

    @api.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": runtime_settings.app_mode.value}

    api.include_router(create_legacy_router())
    api.include_router(
        create_cockpit_router(
            cockpit_authority,
            runtime_settings,
            platform=platform_wire,
            ws_registry=ws_registry,
        )
    )
    api.include_router(create_platform_session_router(platform_service, runtime_settings))
    api.include_router(
        create_platform_admin_router(
            sessions=platform_service,
            admin=platform_admin,
            audit=platform_audit,
            settings=runtime_settings,
        )
    )
    return api


app = create_app()
