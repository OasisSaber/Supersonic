from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import RuntimeSettings
from ..platform.persistence import DatabaseUnavailable, MigrationRequired
from ..platform.sessions import (
    AuditPersistenceFailure,
    CredentialStoreInvalid,
    InvalidCredentials,
    InvalidSession,
    IssuedSession,
    LoginThrottled,
    SessionIdentity,
)


class PlatformUnavailable(RuntimeError):
    """The optional platform service has not been composed."""


class PlatformSessionService(Protocol):
    async def login(
        self, username: str, password: str, remote_client_key: str
    ) -> IssuedSession: ...

    async def logout(self, raw_secret: str) -> bool: ...

    async def resolve(self, raw_secret: str) -> SessionIdentity: ...


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


NO_STORE = {"Cache-Control": "no-store"}


def _error(status: int, code: str, message: str, **headers: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers={**NO_STORE, **headers},
    )


def _origin_error(request: Request, settings: RuntimeSettings) -> JSONResponse | None:
    if request.headers.get("origin") != settings.platform_ui_origin:
        return _error(403, "origin_forbidden", "Request origin is not allowed.")
    return None


def _required_cookie(request: Request, settings: RuntimeSettings) -> str | None:
    value = request.cookies.get(settings.platform_cookie.name)
    return value or None


def _identity_payload(value: IssuedSession | SessionIdentity) -> dict[str, str]:
    if isinstance(value, IssuedSession):
        user_id = value.user_id
        role = value.role
        session_id = value.platform_session_id
    else:
        user_id = value.principal.user_id
        role = value.principal.role
        session_id = value.principal.session_id
    expires_at = value.expires_at.isoformat().replace("+00:00", "Z")
    return {
        "userId": user_id,
        "displayName": value.display_name,
        "role": role.value,
        "platformSessionId": session_id,
        "expiresAt": expires_at,
    }


def _service_error(error: Exception) -> JSONResponse:
    if isinstance(error, LoginThrottled):
        return _error(
            429,
            "login_throttled",
            "Too many login attempts.",
            **{"Retry-After": str(error.retry_after)},
        )
    mappings: tuple[tuple[type[Exception], int, str, str], ...] = (
        (InvalidCredentials, 401, "invalid_credentials", "Invalid username or password."),
        (InvalidSession, 401, "session_invalid", "Invalid or expired session."),
        (DatabaseUnavailable, 503, "database_unavailable", "Platform database is unavailable."),
        (MigrationRequired, 503, "migration_required", "Platform database migration is required."),
        (PlatformUnavailable, 503, "platform_unavailable", "Platform service is unavailable."),
        (
            CredentialStoreInvalid,
            503,
            "credential_store_invalid",
            "Stored credentials cannot be safely verified.",
        ),
        (
            AuditPersistenceFailure,
            503,
            "audit_persistence_failure",
            "The result could not be durably audited.",
        ),
    )
    for error_type, status, code, message in mappings:
        if isinstance(error, error_type):
            return _error(status, code, message)
    raise error


def create_platform_session_router(
    service: PlatformSessionService,
    settings: RuntimeSettings,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/platform/session/login")
    async def login(request: Request) -> Response:
        if origin_error := _origin_error(request, settings):
            return origin_error
        try:
            body = LoginRequest.model_validate(await request.json())
        except (ValidationError, ValueError):
            return _error(422, "invalid_request", "Login request is invalid.")
        remote_client_key = request.client.host if request.client is not None else "unknown-client"
        try:
            issued = await service.login(body.username, body.password, remote_client_key)
        except Exception as error:
            return _service_error(error)
        response = JSONResponse(_identity_payload(issued), headers=NO_STORE)
        cookie = settings.platform_cookie
        response.set_cookie(
            cookie.name,
            issued.token,
            httponly=cookie.httponly,
            secure=cookie.secure,
            samesite=cookie.samesite,
            path=cookie.path,
            domain=cookie.domain,
        )
        return response

    @router.post("/api/platform/session/logout")
    async def logout(request: Request) -> Response:
        if origin_error := _origin_error(request, settings):
            return origin_error
        raw_secret = _required_cookie(request, settings)
        if raw_secret is None:
            return _error(401, "session_required", "A platform session is required.")
        try:
            await service.logout(raw_secret)
        except Exception as error:
            return _service_error(error)
        response = JSONResponse({"loggedOut": True}, headers=NO_STORE)
        cookie = settings.platform_cookie
        response.delete_cookie(
            cookie.name,
            path=cookie.path,
            domain=cookie.domain,
            secure=cookie.secure,
            httponly=cookie.httponly,
            samesite=cookie.samesite,
        )
        return response

    @router.get("/api/platform/session/me")
    async def me(request: Request) -> Response:
        raw_secret = _required_cookie(request, settings)
        if raw_secret is None:
            return _error(401, "session_required", "A platform session is required.")
        try:
            current = await service.resolve(raw_secret)
        except Exception as error:
            return _service_error(error)
        return JSONResponse(_identity_payload(current), headers=NO_STORE)

    return router
