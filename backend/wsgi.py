#!/usr/bin/env python3
"""WSGI entrypoint for Silk / NGINX Unit.

Silk Python apps use the WSGI model (see https://silk.uvm.edu/manual/python/).
FastAPI is ASGI, so we bridge with a2wsgi.
"""

from a2wsgi import ASGIMiddleware

from app.main import app as asgi_app

application = ASGIMiddleware(asgi_app)
