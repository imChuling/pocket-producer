from .admin import router as admin_router
from .fragments import router as fragments_router
from .notifications import router as notifications_router
from .projects import router as projects_router
from .ranking import router as ranking_router

__all__ = [
    "fragments_router",
    "projects_router",
    "notifications_router",
    "admin_router",
    "ranking_router",
]
