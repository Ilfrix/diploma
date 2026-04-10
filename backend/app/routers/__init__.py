from app.routers.auth import router as auth_router
from app.routers.samples import router as samples_router
from app.routers.search import router as search_router

__all__ = ["auth_router", "samples_router", "search_router"]
