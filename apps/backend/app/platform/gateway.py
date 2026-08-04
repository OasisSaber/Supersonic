from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from ..cockpit.errors import CommandRejected
from ..cockpit.service import CockpitService
from ..contracts.v1 import CommandEnvelopeV1, CommandName, EndpointId, SnapshotEnvelopeV1
from .audit import AuditBuffer, AuditFallback, AuditSink
from .authorization import RoleCommandPolicy
from .errors import AuditUnavailable, RoleForbidden
from .models import AuditRecord, AuditResult, Principal
from .sanitization import sanitize_parameters

_MANAGEMENT_COMMANDS = frozenset(
    {
        CommandName.SET_THEME,
        CommandName.SET_SYSTEM_MODE,
        CommandName.RESET_SESSION,
    }
)
_SAFETY_CRITICAL_COMMANDS = frozenset(
    {
        CommandName.ACKNOWLEDGE_RISK,
        CommandName.RESOLVE_RISK,
    }
)


@dataclass(frozen=True, slots=True)
class GatewayResult:
    envelope: SnapshotEnvelopeV1
    audit_degraded: bool = False


class AuthorizedCockpitGateway:
    """Future platform boundary around the existing authoritative CockpitService.

    This class is intentionally not connected to the public router until server-side
    sessions and the PostgreSQL adapter pass the G3/G4 approval gates.
    """

    def __init__(
        self,
        authority: CockpitService,
        audit_sink: AuditSink,
        *,
        policy: RoleCommandPolicy | None = None,
        fallback_buffer: AuditFallback | None = None,
    ) -> None:
        self._authority = authority
        self._audit_sink = audit_sink
        self._policy = policy or RoleCommandPolicy()
        self._fallback = fallback_buffer or AuditBuffer()

    async def apply_command(
        self,
        principal: Principal,
        command: CommandEnvelopeV1,
        *,
        server_endpoint: EndpointId,
    ) -> GatewayResult:
        try:
            self._policy.authorize(principal, command.payload.name)
        except RoleForbidden:
            await self._record(
                principal,
                command,
                server_endpoint,
                result=AuditResult.REJECTED,
                error_code="role_forbidden",
                allow_fallback=True,
            )
            raise

        management_command = command.payload.name in _MANAGEMENT_COMMANDS
        if management_command:
            if not await self._audit_sink.is_available():
                raise AuditUnavailable("Management commands require an available audit sink.")
            # Persist an intent before mutating the in-memory authority. A later outcome
            # write may degrade, but the command will never be completely unaudited.
            await self._record(
                principal,
                command,
                server_endpoint,
                result=AuditResult.ATTEMPTED,
                allow_fallback=False,
            )

        try:
            envelope = await self._authority.apply_command(
                command,
                server_endpoint=server_endpoint,
            )
        except CommandRejected:
            await self._record(
                principal,
                command,
                server_endpoint,
                result=AuditResult.REJECTED,
                error_code="command_rejected",
                allow_fallback=True,
            )
            raise
        except Exception:
            await self._record(
                principal,
                command,
                server_endpoint,
                result=AuditResult.ERROR,
                error_code="internal_error",
                allow_fallback=True,
            )
            raise

        degraded = not await self._record(
            principal,
            command,
            server_endpoint,
            result=AuditResult.SUCCEEDED,
            allow_fallback=(
                management_command
                or command.payload.name in _SAFETY_CRITICAL_COMMANDS
            ),
        )
        return GatewayResult(envelope=envelope, audit_degraded=degraded)

    async def _record(
        self,
        principal: Principal,
        command: CommandEnvelopeV1,
        endpoint: EndpointId,
        *,
        result: AuditResult,
        error_code: str | None = None,
        allow_fallback: bool,
    ) -> bool:
        record = AuditRecord(
            audit_id=str(uuid4()),
            occurred_at=datetime.now(UTC),
            actor_user_id=principal.user_id,
            actor_role=principal.role,
            actor_session_id=principal.session_id,
            endpoint=endpoint.value,
            command_name=command.payload.name.value,
            correlation_id=str(command.correlation_id),
            result=result,
            parameters=sanitize_parameters(command.payload.parameters),
            error_code=error_code,
        )
        try:
            await self._audit_sink.append(record)
            return True
        except AuditUnavailable:
            if not allow_fallback:
                raise
            self._fallback.append(replace(record, result=AuditResult.DEGRADED))
            return False
