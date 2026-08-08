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
from .models import AuditDelivery, AuditRecord, AuditResult, Principal
from .sanitization import sanitize_parameters

_MANAGEMENT_COMMANDS = frozenset(
    {
        CommandName.SET_THEME,
        CommandName.SET_SYSTEM_MODE,
        CommandName.RESET_SESSION,
    }
)


@dataclass(frozen=True, slots=True)
class GatewayResult:
    envelope: SnapshotEnvelopeV1
    audit_delivery: AuditDelivery = AuditDelivery.PRIMARY

    @property
    def audit_degraded(self) -> bool:
        return self.audit_delivery is not AuditDelivery.PRIMARY

    @property
    def audit_recorded(self) -> bool:
        return self.audit_delivery is not AuditDelivery.LOST


class AuthorizedCockpitGateway:
    """Future platform boundary around the authoritative CockpitService.

    The public router must not use this gateway until server-side sessions and the
    PostgreSQL adapter pass the G3/G4 gates. Management commands require a primary
    intent record before mutation. Other commands may use a bounded fallback so a
    primary audit outage never turns a successful state mutation into a false error.
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
        except RoleForbidden as exc:
            delivery = await self._record(
                principal,
                command,
                server_endpoint,
                result=AuditResult.REJECTED,
                error_code="role_forbidden",
                allow_fallback=True,
            )
            self._note_lost_delivery(exc, delivery)
            raise

        management_command = command.payload.name in _MANAGEMENT_COMMANDS
        if management_command:
            if not await self._primary_available():
                raise AuditUnavailable("Management commands require an available audit sink.")
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
        except CommandRejected as exc:
            delivery = await self._record(
                principal,
                command,
                server_endpoint,
                result=AuditResult.REJECTED,
                error_code=exc.code,
                allow_fallback=True,
            )
            self._note_lost_delivery(exc, delivery)
            raise
        except Exception as exc:
            delivery = await self._record(
                principal,
                command,
                server_endpoint,
                result=AuditResult.ERROR,
                error_code="internal_error",
                allow_fallback=True,
            )
            self._note_lost_delivery(exc, delivery)
            raise

        delivery = await self._record(
            principal,
            command,
            server_endpoint,
            result=AuditResult.SUCCEEDED,
            allow_fallback=True,
        )
        return GatewayResult(envelope=envelope, audit_delivery=delivery)

    async def _record(
        self,
        principal: Principal,
        command: CommandEnvelopeV1,
        endpoint: EndpointId,
        *,
        result: AuditResult,
        error_code: str | None = None,
        allow_fallback: bool,
    ) -> AuditDelivery:
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
            await self._append_primary(record)
            return AuditDelivery.PRIMARY
        except AuditUnavailable:
            if not allow_fallback:
                raise
            fallback_record = replace(record, delivery=AuditDelivery.FALLBACK)
            try:
                self._fallback.append(fallback_record)
            except Exception:
                return AuditDelivery.LOST
            return AuditDelivery.FALLBACK

    async def _primary_available(self) -> bool:
        try:
            return await self._audit_sink.is_available()
        except AuditUnavailable:
            return False
        except Exception as exc:
            raise AuditUnavailable("Audit availability check failed.") from exc

    async def _append_primary(self, record: AuditRecord) -> None:
        try:
            await self._audit_sink.append(record)
        except AuditUnavailable:
            raise
        except Exception as exc:
            raise AuditUnavailable("Primary audit append failed.") from exc

    @staticmethod
    def _note_lost_delivery(exc: Exception, delivery: AuditDelivery) -> None:
        if delivery is AuditDelivery.LOST:
            exc.add_note("The command outcome could not be written to primary or fallback audit.")
