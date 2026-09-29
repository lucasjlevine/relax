#!/usr/bin/env python3
"""WSGI entrypoint for Silk / NGINX Unit.

Unit may present /relax-api/health as PATH_INFO=/health (prefix stripped).
"""

from __future__ import annotations

import os
import sys
import traceback

_API_ROOT = (os.environ.get("API_ROOT_PATH") or "/api").rstrip("/") or "/api"
_DEBUG_LOG = os.environ.get("RELAX_WSGI_DEBUG", "")


def _log(msg: str) -> None:
    if not _DEBUG_LOG:
        return
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def _full_path(environ: dict) -> str:
    script = environ.get("SCRIPT_NAME") or ""
    path = environ.get("PATH_INFO") or ""
    if script and not path.startswith(script):
        if not path.startswith("/"):
            path = "/" + path
        return script.rstrip("/") + path
    return path or "/"


def _is_health(environ: dict) -> bool:
    full = _full_path(environ).rstrip("/")
    path = (environ.get("PATH_INFO") or "").rstrip("/")
    return (
        path == "/health"
        or path.endswith("/health")
        or full == f"{_API_ROOT}/health"
        or full == "/api/health"
        or full.endswith("/health")
    )


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


def _json_error(start_response, status: str, detail: str, header: str):
    # Keep detail ASCII-safe for logs/clients
    safe = detail.replace("\\", "\\\\").replace('"', '\\"')[:800]
    body = f'{{"status":"error","detail":"{safe}"}}'.encode()
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("X-Relax-Backend", header),
        ],
    )
    return [body]


def _normalize_environ(environ: dict) -> dict:
    """Ensure PATH_INFO is under API_ROOT for FastAPI routing."""
    path = environ.get("PATH_INFO") or ""
    script = (environ.get("SCRIPT_NAME") or "").rstrip("/")

    if path.startswith(_API_ROOT) or path.startswith("/api"):
        if script:
            environ = dict(environ)
            environ["SCRIPT_NAME"] = ""
        return environ

    # Prefix was stripped: /health, /datasets, …
    environ = dict(environ)
    if not path.startswith("/"):
        path = "/" + path
    environ["PATH_INFO"] = _API_ROOT + path
    environ["SCRIPT_NAME"] = ""
    return environ


def _load_asgi_wsgi():
    from a2wsgi import ASGIMiddleware
    from app.main import app as asgi_app

    return ASGIMiddleware(asgi_app)


_asgi_wsgi = None


def application(environ, start_response):
    global _asgi_wsgi

    _log(
        f"PATH_INFO={environ.get('PATH_INFO')!r} "
        f"SCRIPT_NAME={environ.get('SCRIPT_NAME')!r} "
        f"full={_full_path(environ)!r}"
    )

    if _is_health(environ):
        return _health(environ, start_response)

    try:
        if _asgi_wsgi is None:
            _asgi_wsgi = _load_asgi_wsgi()
    except Exception:
        _log(traceback.format_exc())
        return _json_error(
            start_response,
            "500 Internal Server Error",
            traceback.format_exc().splitlines()[-1],
            "wsgi-import-error",
        )

    try:
        environ = _normalize_environ(environ)

        def _start_response(status, headers, exc_info=None):
            headers = list(headers)
            headers.append(("X-Relax-Backend", "fastapi"))
            return start_response(status, headers, exc_info)

        return _asgi_wsgi(environ, _start_response)
    except Exception:
        _log(traceback.format_exc())
        print(traceback.format_exc(), file=sys.stderr)
        return _json_error(
            start_response,
            "500 Internal Server Error",
            traceback.format_exc().splitlines()[-1],
            "wsgi-runtime-error",
        )
