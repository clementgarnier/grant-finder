#!/usr/bin/env python3
"""Single-process entrypoint that runs both MCP servers behind one ASGI app.

The two servers (irs-990, grants-gov) stay fully independent - separate
server.py files, separate requirements.txt, separate FastMCP instances and
GraphQL schemas. This module only mounts their `streamable_http_app()`s
under one Starlette app and one port, so both can share a single deployed
service/container instead of two (see docker/mcp/Dockerfile and
deploy/app.yaml) - the MCP servers themselves aren't merged, just their
hosting.

Each irs-990/server.py and grants-gov/server.py is loaded by file path
(not `import server`, since both modules share that filename) and left
otherwise untouched: running either one directly, e.g. for local debugging,
still works exactly as before.
"""
import importlib.util
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from types import ModuleType

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Mount
from strawberry.asgi import GraphQL

ROOT = Path(__file__).resolve().parent

# Matches deploy/app.yaml's `domains:` entry and plugin/mcp.config.release.json.
PRODUCTION_HOST = "grant-finder.clementgarnier.com"


class OriginVerifyMiddleware:
    """Rejects requests missing the `x-origin-verify` header, production only.

    Guards against the service being hit directly (bypassing whatever fronts
    it, e.g. a CDN/proxy that's supposed to inject this header) once it's on
    the public internet. Skipped locally (docker-compose doesn't set
    ENVIRONMENT) so `docker compose up` and direct `python server.py` runs
    don't need the secret configured.
    """

    def __init__(self, app):
        self.app = app
        self.enabled = os.environ.get("ENVIRONMENT") == "production"
        if self.enabled:
            self.secret = os.environ["X_ORIGIN_VERIFY_SECRET"]

    async def __call__(self, scope, receive, send):
        if self.enabled and scope["type"] == "http":
            headers = Headers(scope=scope)
            if headers.get("x-origin-verify") != self.secret:
                response = PlainTextResponse("Forbidden", status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


irs990 = _load_module("irs990_server", ROOT / "irs-990" / "server.py")
grants_gov = _load_module("grantsgov_server", ROOT / "grants-gov" / "server.py")

if os.environ.get("ENVIRONMENT") == "production":
    # Each FastMCP() call above defaults to host="127.0.0.1", which makes the
    # SDK's DNS-rebinding protection allow only localhost Host headers - fine
    # for `docker compose up`, but it 421s every request once this is running
    # behind the real domain. Widen it to the production host instead of
    # disabling the protection outright.
    production_transport_security = TransportSecuritySettings(
        allowed_hosts=[PRODUCTION_HOST], allowed_origins=[f"https://{PRODUCTION_HOST}"]
    )
    irs990.mcp.settings.transport_security = production_transport_security
    grants_gov.mcp.settings.transport_security = production_transport_security

irs990_app = irs990.mcp.streamable_http_app()
grants_gov_app = grants_gov.mcp.streamable_http_app()

# Troubleshooting-only GraphQL/GraphiQL mounts, same convention each server
# used standalone - not meant to be reachable outside localhost/the docker
# network. Mounted onto each sub-app directly (as each server's own main()
# used to do) so that, once nested under the /irs-990 and /grants-gov
# prefixes below, they land at .../irs-990/graphql and .../grants-gov/graphql.
irs990_app.mount("/graphql", GraphQL(irs990.schema, graphql_ide="graphiql"))
grants_gov_app.mount("/graphql", GraphQL(grants_gov.schema, graphql_ide="graphiql"))


@asynccontextmanager
async def lifespan(app):
    # Mounting a Starlette sub-app doesn't forward lifespan events on its
    # own, and each FastMCP app's streamable-http session manager relies on
    # its lifespan running to start its task group - so both sub-lifespans
    # have to be entered explicitly here.
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(irs990_app.router.lifespan_context(irs990_app))
        await stack.enter_async_context(grants_gov_app.router.lifespan_context(grants_gov_app))
        yield


app = Starlette(
    routes=[
        Mount("/irs-990", app=irs990_app),
        Mount("/grants-gov", app=grants_gov_app),
    ],
    lifespan=lifespan,
    middleware=[Middleware(OriginVerifyMiddleware)],
)


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


if __name__ == "__main__":
    main()
