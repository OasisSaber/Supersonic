from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from ..config import RuntimeSettings
from ..platform.admin import (
    AdminMutationResult,
    AdminServiceError,
    SessionSummary,
    UserSummary,
)
from ..platform.audit_identity import AuditEventConflict
from ..platform.models import AuditCursor, AuditEvent, AuditPage, Principal, Role
from ..platform.persistence import DatabaseUnavailable, MigrationRequired
from ..platform.sessions import InvalidSession, SessionIdentity
from .platform_session_router import PlatformUnavailable

NO_STORE = {"Cache-Control": "no-store"}
_MAX_CURSOR_CHARS = 512
_BASE64URL_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
_BodyModel = TypeVar("_BodyModel", bound=BaseModel)


class SessionResolver(Protocol):
    async def resolve(self, raw_secret: str) -> SessionIdentity: ...


class UserAdminPort(Protocol):
    async def list_users(
        self, actor: Principal, *, limit: int = 100
    ) -> tuple[UserSummary, ...]: ...

    async def list_sessions(
        self, actor: Principal, user_id: str, *, limit: int = 100
    ) -> tuple[SessionSummary, ...]: ...

    async def change_role(
        self, actor: Principal, user_id: str, new_role: Role
    ) -> AdminMutationResult: ...

    async def set_disabled(
        self, actor: Principal, user_id: str, *, disabled: bool
    ) -> AdminMutationResult: ...

    async def revoke_session(
        self,
        actor: Principal,
        platform_session_id: str,
        *,
        reason: str = "admin_revoke",
    ) -> AdminMutationResult: ...


class AuditQueryPort(Protocol):
    async def list_for_role(
        self,
        role: Role,
        *,
        cursor: AuditCursor | None = None,
        limit: int = 50,
    ) -> AuditPage: ...


class RoleChangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


class DisabledBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disabled: StrictBool


class RevokeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="admin_revoke", min_length=1, max_length=64)


def create_platform_admin_router(
    *,
    sessions: SessionResolver,
    admin: UserAdminPort,
    audit: AuditQueryPort,
    settings: RuntimeSettings,
) -> APIRouter:
    router = APIRouter()

    async def resolve_identity(request: Request) -> SessionIdentity | JSONResponse:
        raw_secret = request.cookies.get(settings.platform_cookie.name)
        if not raw_secret:
            return _error(401, "session_required", "A platform session is required.")
        try:
            return await sessions.resolve(raw_secret)
        except InvalidSession:
            return _error(401, "session_invalid", "Invalid or expired session.")
        except DatabaseUnavailable:
            return _error(503, "database_unavailable", "Platform database is unavailable.")
        except MigrationRequired:
            return _error(
                503,
                "migration_required",
                "Platform database migration is required.",
            )
        except PlatformUnavailable:
            return _error(503, "platform_unavailable", "Platform service is unavailable.")

    def require_origin(request: Request) -> JSONResponse | None:
        if request.headers.get("origin") != settings.platform_ui_origin:
            return _error(403, "origin_forbidden", "Request origin is not allowed.")
        return None

    @router.get("/api/platform/admin/users")
    async def users(request: Request) -> Response:
        current = await resolve_identity(request)
        if isinstance(current, JSONResponse):
            return current
        limit = _bounded_limit(request, default=100)
        if limit is None:
            return _error(422, "invalid_request", "Request parameters are invalid.")
        try:
            values = await admin.list_users(current.principal, limit=limit)
        except Exception as error:
            return _admin_error(error)
        return JSONResponse(
            {"users": [_user_payload(value) for value in values]},
            headers=NO_STORE,
        )

    @router.get("/api/platform/admin/users/{user_id}/sessions")
    async def user_sessions(user_id: str, request: Request) -> Response:
        current = await resolve_identity(request)
        if isinstance(current, JSONResponse):
            return current
        limit = _bounded_limit(request, default=100)
        if limit is None:
            return _error(422, "invalid_request", "Request parameters are invalid.")
        try:
            values = await admin.list_sessions(current.principal, user_id, limit=limit)
        except Exception as error:
            return _admin_error(error)
        return JSONResponse(
            {"sessions": [_session_payload(value) for value in values]},
            headers=NO_STORE,
        )

    @router.post("/api/platform/admin/users/{user_id}/role")
    async def change_role(user_id: str, request: Request) -> Response:
        if origin_error := require_origin(request):
            return origin_error
        current = await resolve_identity(request)
        if isinstance(current, JSONResponse):
            return current
        body = await _validated_body(request, RoleChangeBody)
        if isinstance(body, JSONResponse):
            return body
        try:
            result = await admin.change_role(current.principal, user_id, body.role)
        except Exception as error:
            return _admin_error(error)
        return JSONResponse(_mutation_payload(result), headers=NO_STORE)

    @router.post("/api/platform/admin/users/{user_id}/disabled")
    async def set_disabled(user_id: str, request: Request) -> Response:
        if origin_error := require_origin(request):
            return origin_error
        current = await resolve_identity(request)
        if isinstance(current, JSONResponse):
            return current
        body = await _validated_body(request, DisabledBody)
        if isinstance(body, JSONResponse):
            return body
        try:
            result = await admin.set_disabled(
                current.principal,
                user_id,
                disabled=body.disabled,
            )
        except Exception as error:
            return _admin_error(error)
        return JSONResponse(_mutation_payload(result), headers=NO_STORE)

    @router.post("/api/platform/admin/sessions/{session_id}/revoke")
    async def revoke_session(session_id: str, request: Request) -> Response:
        if origin_error := require_origin(request):
            return origin_error
        current = await resolve_identity(request)
        if isinstance(current, JSONResponse):
            return current
        body = await _validated_body(request, RevokeBody)
        if isinstance(body, JSONResponse):
            return body
        if not body.reason.strip():
            return _error(422, "invalid_request", "Request body is invalid.")
        try:
            result = await admin.revoke_session(
                current.principal,
                session_id,
                reason=body.reason,
            )
        except Exception as error:
            return _admin_error(error)
        return JSONResponse(_mutation_payload(result), headers=NO_STORE)

    @router.get("/api/platform/audit")
    async def audit_history(request: Request) -> Response:
        current = await resolve_identity(request)
        if isinstance(current, JSONResponse):
            return current
        limit = _bounded_limit(request, default=50)
        if limit is None:
            return _error(422, "invalid_request", "Request parameters are invalid.")
        raw_cursor = request.query_params.get("cursor")
        try:
            cursor = _decode_cursor(raw_cursor) if raw_cursor is not None else None
        except ValueError:
            return _error(422, "invalid_cursor", "Audit cursor is invalid.")
        try:
            page = await audit.list_for_role(
                current.principal.role,
                cursor=cursor,
                limit=limit,
            )
        except DatabaseUnavailable:
            return _error(503, "database_unavailable", "Platform database is unavailable.")
        except MigrationRequired:
            return _error(
                503,
                "migration_required",
                "Platform database migration is required.",
            )
        except PlatformUnavailable:
            return _error(503, "platform_unavailable", "Platform service is unavailable.")
        return JSONResponse(_audit_page_payload(page), headers=NO_STORE)

    return router


async def _validated_body(
    request: Request,
    model: type[_BodyModel],
) -> _BodyModel | JSONResponse:
    try:
        return model.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        return _error(422, "invalid_request", "Request body is invalid.")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers=NO_STORE,
    )


def _admin_error(error: Exception) -> JSONResponse:
    if isinstance(error, AdminServiceError):
        return _error(error.status_code, error.code, error.message)
    if isinstance(error, DatabaseUnavailable):
        return _error(503, "database_unavailable", "Platform database is unavailable.")
    if isinstance(error, MigrationRequired):
        return _error(503, "migration_required", "Platform database migration is required.")
    if isinstance(error, PlatformUnavailable):
        return _error(503, "platform_unavailable", "Platform service is unavailable.")
    if isinstance(error, AuditEventConflict):
        return _error(503, "audit_conflict", "Audit integrity conflict was detected.")
    raise error


def _bounded_limit(request: Request, *, default: int) -> int | None:
    raw = request.query_params.get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if 1 <= value <= 100 else None


def _user_payload(value: UserSummary) -> dict[str, Any]:
    return {
        "id": value.id,
        "username": value.username_norm,
        "displayName": value.display_name,
        "role": value.role.value,
        "disabledAt": _iso(value.disabled_at),
        "createdAt": _iso(value.created_at),
        "updatedAt": _iso(value.updated_at),
    }


def _session_payload(value: SessionSummary) -> dict[str, Any]:
    return {
        "id": value.id,
        "userId": value.user_id,
        "createdAt": _iso(value.created_at),
        "expiresAt": _iso(value.expires_at),
        "lastSeenAt": _iso(value.last_seen_at),
        "revokedAt": _iso(value.revoked_at),
        "revokeReason": value.revoke_reason,
    }


def _mutation_payload(value: AdminMutationResult) -> dict[str, Any]:
    failed = list(value.revoke_propagation_failed_ids)
    return {
        "changed": value.changed,
        "revokedSessionIds": list(value.revoked_session_ids),
        "revokePropagation": "degraded" if failed else "complete",
        "failedRevokePropagationSessionIds": failed,
    }


def _audit_page_payload(page: AuditPage) -> dict[str, Any]:
    return {
        "events": [_audit_event_payload(event) for event in page.events],
        "nextCursor": _encode_cursor(page.next_cursor) if page.next_cursor else None,
    }


def _audit_event_payload(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "occurredAt": _iso(event.occurred_at),
        "action": event.action,
        "result": event.result.value,
        "delivery": event.delivery.value,
        "actorUserId": event.actor_user_id,
        "actorPlatformSessionId": event.actor_platform_session_id,
        "actorRole": event.actor_role.value if event.actor_role else None,
        "endpoint": event.endpoint,
        "cockpitSessionId": event.cockpit_session_id,
        "commandName": event.command_name,
        "correlationId": event.correlation_id,
        "targetType": event.target_type,
        "targetId": event.target_id,
        "parameters": event.parameters,
        "errorCode": event.error_code,
        "sourceType": event.source_type,
    }


def _encode_cursor(cursor: AuditCursor) -> str:
    payload = json.dumps(
        {
            "t": _iso(cursor.occurred_at.astimezone(UTC)),
            "id": str(UUID(cursor.event_id)),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(value: str) -> AuditCursor:
    if (
        not value
        or len(value) > _MAX_CURSOR_CHARS
        or len(value) % 4 == 1
        or any(character not in _BASE64URL_CHARS for character in value)
    ):
        raise ValueError("invalid cursor")
    padding = "=" * (-len(value) % 4)
    try:
        raw = base64.b64decode(value + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"t", "id"}:
            raise ValueError("invalid cursor")
        timestamp = payload["t"]
        event_id_value = payload["id"]
        if not isinstance(timestamp, str) or not isinstance(event_id_value, str):
            raise ValueError("invalid cursor")
        if not timestamp.endswith("Z"):
            raise ValueError("invalid cursor")
        occurred_at = datetime.fromisoformat(f"{timestamp[:-1]}+00:00")
        event_id = str(UUID(event_id_value))
        if event_id != event_id_value:
            raise ValueError("invalid cursor")
        cursor = AuditCursor(occurred_at=occurred_at, event_id=event_id)
        if _encode_cursor(cursor) != value:
            raise ValueError("invalid cursor")
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as error:
        raise ValueError("invalid cursor") from error
    return cursor


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")
