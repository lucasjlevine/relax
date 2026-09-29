#!/usr/bin/env python3
"""WSGI entrypoint for Silk / NGINX Unit.

Silk Python apps use the WSGI model (https://silk.uvm.edu/manual/python/).
FastAPI is ASGI, so we bridge with a2wsgi.

On Silk, URI is /relax-api* and API_ROOT_PATH=/relax-api.
"""

from __future__ import annotations

import os

# Match FastAPI api_root_path (Silk sets API_ROOT_PATH=/relax-api)
_API_ROOT = (os.environ.get("API_ROOT_PATH") or "/api").rstrip("/") or "/api"


def _full_path(environ: dict) -> str:
    script = environ.get("SCRIPT_NAME") or ""
    path = environ.get("PATH_INFO") or ""
    if script and not path.startswith(script):
        if not path.startswith("/"):
            path = "/" + path
        return script.rstrip("/") + path
    return path or "/"


def _health(_environ, start_response):
    body = b'{"status":"ok","via":"wsgi"}'
    start_response(
        "200 OK",
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Relax-Backend", "wsgi-health"),
        ],
    )
    return [body]


def _load_asgi_wsgi():
    from a2wsgi import ASGIMiddleware
    from app.main import app as asgi_app

    return ASGIMiddleware(asgi_app)


_asgi_wsgi = None


def application(environ, start_response):
    global _asgi_wsgi

    full = _full_path(environ)

    if full.rstrip("/") in (f"{_API_ROOT}/health", "/api/health"):
        return _health(environ, start_response)

    try:
        if _asgi_wsgi is None:
            _asgi_wsgi = _load_asgi_wsgi()
    except Exception as exc:  # noqa: BLE001
        body = f'{{"status":"error","detail":{exc!r}}}'.encode()
        start_response(
            "500 Internal Server Error",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("X-Relax-Backend", "wsgi-import-error"),
            ],
        )
        return [body]

    # Unit may set SCRIPT_NAME to the app prefix; FastAPI expects full paths.
    script = (environ.get("SCRIPT_NAME") or "").rstrip("/")
    path = environ.get("PATH_INFO") or ""
    if script in (_API_ROOT, "/api", "/relax-api") and not path.startswith(script):
        environ = dict(environ)
        environ["PATH_INFO"] = script + (path if path.startswith("/") else f"/{path}")
        environ["SCRIPT_NAME"] = ""

    def _start_response(status, headers, exc_info=None):
        headers = list(headers)
        headers.append(("X-Relax-Backend", "fastapi"))
        return start_response(status, headers, exc_info)

    return _asgi_wsgi(environ, _start_response)
