"""
BC MCP Proxy for ChatGPT
─────────────────────────
ChatGPT cannot send custom HTTP headers on MCP connectors.
BC MCP server requires TenantId, EnvironmentName, and Company headers.

This proxy sits between ChatGPT and BC:
  ChatGPT  ──►  this proxy  ──►  mcp.businesscentral.dynamics.com
                (adds headers)

Deploy anywhere that gives you an HTTPS URL (Railway, Render, etc.)
and paste that URL into ChatGPT's Plugins as a custom MCP connector.
"""

import os
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager

# ── Config (set via environment variables) ──────────────────────────

BC_MCP_URL    = os.getenv("BC_MCP_URL", "https://mcp.businesscentral.dynamics.com")
BC_TENANT_ID  = os.getenv("BC_TENANT_ID", "")
BC_ENVIRONMENT = os.getenv("BC_ENVIRONMENT", "Production")
BC_COMPANY    = os.getenv("BC_COMPANY", "CRONUS USA, Inc.")
BC_CONFIG_NAME = os.getenv("BC_CONFIG_NAME", "")  # optional MCP configuration name

PORT = int(os.getenv("PORT", 8000))


# ── App lifecycle ───────────────────────────────────────────────────

http_client: httpx.AsyncClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(300.0, connect=30.0),
        follow_redirects=False,
    )
    yield
    await http_client.aclose()


app = FastAPI(title="BC MCP Proxy for ChatGPT", lifespan=lifespan)


# ── Health check ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "target": BC_MCP_URL,
        "tenant": BC_TENANT_ID[:8] + "..." if BC_TENANT_ID else "NOT SET",
        "environment": BC_ENVIRONMENT,
        "company": BC_COMPANY,
    }


# ── Header injection ───────────────────────────────────────────────

SKIP_REQUEST_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}
SKIP_RESPONSE_HEADERS = {"transfer-encoding", "connection", "keep-alive"}


def build_upstream_headers(request: Request) -> dict:
    """
    Copy all client headers (auth, accept, content-type, etc.)
    and inject the BC-specific headers that ChatGPT cannot send.
    """
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in SKIP_REQUEST_HEADERS
    }

    # Inject BC headers
    headers["TenantId"] = BC_TENANT_ID
    headers["EnvironmentName"] = BC_ENVIRONMENT
    headers["Company"] = BC_COMPANY

    if BC_CONFIG_NAME:
        headers["ConfigurationName"] = BC_CONFIG_NAME

    return headers


# ── Proxy handler ───────────────────────────────────────────────────

async def _proxy(request: Request, path: str = ""):
    """Forward request to BC MCP server with injected headers."""

    # Validate config
    if not BC_TENANT_ID:
        return JSONResponse(
            status_code=500,
            content={"error": "BC_TENANT_ID environment variable is not set"},
        )

    # Build upstream URL
    target = f"{BC_MCP_URL}/{path}" if path else BC_MCP_URL
    query = str(request.url.query)
    if query:
        target += f"?{query}"

    # Build headers and body
    headers = build_upstream_headers(request)
    body = await request.body()

    # Send request to BC MCP server (streamed)
    upstream_request = http_client.build_request(
        method=request.method,
        url=target,
        headers=headers,
        content=body if body else None,
    )

    upstream_response = await http_client.send(upstream_request, stream=True)

    # Filter hop-by-hop headers from response
    response_headers = {
        key: value
        for key, value in upstream_response.headers.multi_items()
        if key.lower() not in SKIP_RESPONSE_HEADERS
    }

    # Stream response back to ChatGPT
    async def stream_body():
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=upstream_response.status_code,
        headers=response_headers,
    )


# ── Route registration ─────────────────────────────────────────────
# Catch every path including root, .well-known/*, mcp, etc.

ALL_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"]


@app.api_route("/", methods=ALL_METHODS)
async def proxy_root(request: Request):
    return await _proxy(request, path="")


@app.api_route("/{path:path}", methods=ALL_METHODS)
async def proxy_path(request: Request, path: str):
    return await _proxy(request, path=path)


# ── Run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
