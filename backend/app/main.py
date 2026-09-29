from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import datasets, query
from app.config import get_settings
from app.datasets.loader import DatasetCatalog
from app.datasets.ownership import OWNER_COOKIE, ensure_owner_id, set_owner_cookie
from app.datasets.user_store import UserDatasetStore
from app.datasets.working_catalog import WorkingCatalog
from app.models.schemas import HealthResponse


class OwnerCookieMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        cookie_name = settings.owner_cookie_name or OWNER_COOKIE
        existing = request.cookies.get(cookie_name)
        if existing and existing.startswith("own_") and len(existing) >= 12:
            request.state.owner_id = existing
            response = await call_next(request)
            return response
        owner_id = ensure_owner_id(request, response=None)
        response: Response = await call_next(request)
        if cookie_name not in request.cookies:
            set_owner_cookie(response, owner_id)
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    api_root = (settings.api_root_path or "/api").rstrip("/") or "/api"
    app = FastAPI(title="relax API", version="0.3.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(OwnerCookieMiddleware)

    datasets_path = Path(settings.datasets_path)
    if not datasets_path.is_absolute():
        datasets_path = Path(__file__).resolve().parent.parent / datasets_path

    upload_dir = Path(settings.upload_dir)
    if not upload_dir.is_absolute():
        upload_dir = Path(__file__).resolve().parent.parent / upload_dir

    store_dir = Path(settings.user_datasets_dir)
    if not store_dir.is_absolute():
        store_dir = Path(__file__).resolve().parent.parent / store_dir

    static = DatasetCatalog(datasets_path)
    user_store = UserDatasetStore(
        upload_dir, store_dir, settings.max_upload_bytes
    )
    app.state.user_store = user_store
    app.state.catalog = WorkingCatalog(static, user_store)
    app.include_router(datasets.router, prefix=api_root)
    app.include_router(query.router, prefix=api_root)

    @app.get(f"{api_root}/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
