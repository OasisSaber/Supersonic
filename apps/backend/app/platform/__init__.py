"""Platform identity, authorization, and audit ports.

These modules are intentionally not wired into the gp05.v1 router. PostgreSQL and
server-session adapters require the G3 architecture approval gate.
"""

from .audit import AuditBuffer, AuditFallback, AuditSink, InMemoryAuditSink, JsonlAuditBuffer
from .authorization import RoleCommandPolicy
from .gateway import AuthorizedCockpitGateway, GatewayResult
from .models import AuditDelivery, AuditRecord, AuditResult, Principal, Role

__all__ = [
    "AuditBuffer",
    "AuditDelivery",
    "AuditFallback",
    "AuditRecord",
    "AuditResult",
    "AuditSink",
    "AuthorizedCockpitGateway",
    "GatewayResult",
    "InMemoryAuditSink",
    "JsonlAuditBuffer",
    "Principal",
    "Role",
    "RoleCommandPolicy",
]
