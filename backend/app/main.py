from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import datasets, query
from app.config import get_settings
from app.datasets.loader import DatasetCatalog
from app.models.schemas import HealthResponse


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="relax API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    datasets_path = Path(settings.datasets_path)
    if not datasets_path.is_absolute():
        # Resolve relative to backend package root (parent of app/)
        datasets_path = Path(__file__).resolve().parent.parent / datasets_path

    app.state.catalog = DatasetCatalog(datasets_path)
    app.include_router(datasets.router)
    app.include_router(query.router)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
