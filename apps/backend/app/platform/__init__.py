"""Platform identity, authorization, and audit ports.

These modules are dependency-free and intentionally not wired into the gp05.v1 router yet.
The PostgreSQL adapter is staged separately and requires the G3 architecture approval gate.
"""

from .audit import AuditBuffer, AuditFallback, AuditSink, InMemoryAuditSink, JsonlAuditBuffer
from .authorization import RoleCommandPolicy
from .gateway import AuthorizedCockpitGateway, GatewayResult
from .models import AuditRecord, AuditResult, Principal, Role

__all__ = [
    "AuditBuffer",
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
