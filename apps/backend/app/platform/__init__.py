"""Platform identity, authorization, and audit runtime surface.

The composed `PlatformCommandGateway` / `AuditEvent` runtime is the only canonical
command gateway and durable audit model. PostgreSQL and server-session adapters are
wired in the composition root (`app.main`).
"""

from .authorization import RoleCommandPolicy
from .command_gateway import GatewayResult, PlatformCommandGateway
from .models import AuditDelivery, AuditEvent, AuditResult, Principal, Role

__all__ = [
    "AuditDelivery",
    "AuditEvent",
    "AuditResult",
    "GatewayResult",
    "PlatformCommandGateway",
    "Principal",
    "Role",
    "RoleCommandPolicy",
]
