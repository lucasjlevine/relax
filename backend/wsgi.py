#!/usr/bin/env python3
"""WSGI entrypoint for Silk / NGINX Unit.

Silk Python apps use the WSGI model (https://silk.uvm.edu/manual/python/).
FastAPI is ASGI, so we bridge with a2wsgi.

Unit may set SCRIPT_NAME when matching uri=/api* while our routes are
prefixed with /api — merge those back so routing works.
"""

from __future__ import annotations

from a2wsgi import ASGIMiddleware

from app.main import app as asgi_app

_asgi_wsgi = ASGIMiddleware(asgi_app)


def _full_path(environ: dict) -> str:
    script = environ.get("SCRIPT_NAME") or ""
    path = environ.get("PATH_INFO") or ""
    if script and not path.startswith(script):
        # e.g. SCRIPT_NAME=/api PATH_INFO=/health → /api/health
        if not path.startswith("/"):
            path = "/" + path
        return script.rstrip("/") + path
    return path or "/"


def application(environ, start_response):
    full = _full_path(environ)

    # Plain WSGI health — bypasses a2wsgi so we can verify Unit routing.
    if full.rstrip("/") == "/api/health":
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

    # Ensure FastAPI sees the /api/... path it was defined with.
    script = environ.get("SCRIPT_NAME") or ""
    path = environ.get("PATH_INFO") or ""
    if script.rstrip("/") == "/api" and not path.startswith("/api"):
        environ = dict(environ)
        environ["PATH_INFO"] = "/api" + (path if path.startswith("/") else f"/{path}")
        environ["SCRIPT_NAME"] = ""

    def _start_response(status, headers, exc_info=None):
        headers = list(headers)
        headers.append(("X-Relax-Backend", "fastapi"))
        return start_response(status, headers, exc_info)

    return _asgi_wsgi(environ, _start_response)
