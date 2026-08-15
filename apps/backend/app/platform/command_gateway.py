from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from ..cockpit.errors import CommandRejected
from ..cockpit.service import CockpitService
from ..contracts.v1 import CommandEnvelopeV1, CommandName, EndpointId, SnapshotEnvelopeV1
from .audit_identity import AuditEventConflict
from .authorization import RoleCommandPolicy
from .errors import AuditUnavailable, RoleForbidden
from .models import AuditDelivery, AuditEvent, AuditResult, Principal
from .persistence import DatabaseUnavailable

_MANAGEMENT_COMMANDS = frozenset(
    {
        CommandName.SET_THEME,
        CommandName.SET_SYSTEM_MODE,
        CommandName.RESET_SESSION,
    }
)


class AuditEventAppendPort(Protocol):
    """Primary audit port on the Slice C AuditEvent boundary."""

    async def append(self, event: AuditEvent) -> bool: ...


class AuditFallbackPort(Protocol):
    """Bounded fallback for non-management audit facts."""

    def append(self, event: AuditEvent) -> None: ...


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


class PlatformCommandGateway:
    """Join RolePolicy with the endpoint policy and record AuditEvent facts.

    Management commands require a durable `attempted` fact before mutation.
    Other commands may use the bounded fallback so a primary audit outage never
    turns a successful state mutation into a false error. `AuditEventConflict`
    always propagates: a reused UUID with different content is an integrity
    failure, never a fallback candidate.
    """

    def __init__(
        self,
        *,
        authority: CockpitService,
        audit: AuditEventAppendPort,
        policy: RoleCommandPolicy | None = None,
        fallback: AuditFallbackPort | None = None,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._authority = authority
        self._audit = audit
        self._policy = policy or RoleCommandPolicy()
        self._fallback = fallback
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))

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
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return an aware UTC datetime")
        event = AuditEvent(
            id=self._id_factory(),
            occurred_at=now.astimezone(UTC),
            action="cockpit.command",
            result=result,
            delivery=AuditDelivery.PRIMARY,
            actor_user_id=principal.user_id,
            actor_platform_session_id=principal.session_id,
            actor_role=principal.role,
            endpoint=endpoint.value,
            command_name=command.payload.name.value,
            correlation_id=str(command.correlation_id),
            parameters=dict(command.payload.parameters),
            error_code=error_code,
            source_type="local_hmi",
        )
        try:
            await self._audit.append(event)
            return AuditDelivery.PRIMARY
        except AuditEventConflict:
            raise
        except (AuditUnavailable, DatabaseUnavailable):
            if not allow_fallback:
                raise
            return self._append_fallback(event)
        except Exception as exc:
            if not allow_fallback:
                raise AuditUnavailable("Primary audit append failed.") from exc
            return self._append_fallback(event)

    def _append_fallback(self, event: AuditEvent) -> AuditDelivery:
        if self._fallback is None:
            return AuditDelivery.LOST
        try:
            self._fallback.append(event)
            return AuditDelivery.FALLBACK
        except Exception:
            return AuditDelivery.LOST

    @staticmethod
    def _note_lost_delivery(exc: Exception, delivery: AuditDelivery) -> None:
        if delivery is AuditDelivery.LOST:
            exc.add_note("The command outcome could not be written to primary or fallback audit.")
