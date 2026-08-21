from .cockpit_router import create_cockpit_router
from .legacy_router import create_legacy_router
from .platform_admin_router import create_platform_admin_router
from .platform_session_router import create_platform_session_router

__all__ = [
    "create_cockpit_router",
    "create_legacy_router",
    "create_platform_admin_router",
    "create_platform_session_router",
]
