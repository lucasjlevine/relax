"""Owner identity via HttpOnly cookie (no accounts)."""

from __future__ import annotations

import uuid

from fastapi import Request, Response

from app.config import get_settings
from app.datasets.user_store import _new_owner_id

OWNER_COOKIE = "relax_owner"


def ensure_owner_id(request: Request, response: Response | None = None) -> str:
    """Return owner id from cookie, creating and setting one if missing."""
    settings = get_settings()
    cookie_name = settings.owner_cookie_name or OWNER_COOKIE
    existing = request.cookies.get(cookie_name)
    if existing and existing.startswith("own_") and len(existing) >= 12:
        request.state.owner_id = existing
        return existing
    owner_id = _new_owner_id()
    request.state.owner_id = owner_id
    if response is not None:
        response.set_cookie(
            key=cookie_name,
            value=owner_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365 * 2,
            path="/",
        )
    return owner_id


def set_owner_cookie(response: Response, owner_id: str) -> None:
    settings = get_settings()
    cookie_name = settings.owner_cookie_name or OWNER_COOKIE
    response.set_cookie(
        key=cookie_name,
        value=owner_id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 365 * 2,
        path="/",
    )


def owner_from_request(request: Request) -> str:
    """Read owner from request.state (set by middleware) or cookie."""
    owner = getattr(request.state, "owner_id", None)
    if owner:
        return owner
    settings = get_settings()
    cookie_name = settings.owner_cookie_name or OWNER_COOKIE
    existing = request.cookies.get(cookie_name)
    if existing and existing.startswith("own_"):
        request.state.owner_id = existing
        return existing
    # Fallback for tests without middleware cookie set yet
    owner_id = f"own_{uuid.uuid4().hex}"
    request.state.owner_id = owner_id
    return owner_id
