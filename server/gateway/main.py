import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import uvicorn

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [APIGateway]: %(message)s")
logger = logging.getLogger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Shared HTTP client for reverse-proxying with connection pooling
    app.state.http_client = httpx.AsyncClient(timeout=90.0)
    logger.info("API Gateway started.")
    logger.info(f"Routing /api/auth -> {settings.AUTH_SERVICE_URL}")
    logger.info(f"Routing /api/projects -> {settings.PROJECT_SERVICE_URL}")
    logger.info(f"Routing /api/projects/:id/generate -> {settings.AI_SERVICE_URL}")
    yield
    await app.state.http_client.aclose()
    logger.info("API Gateway shut down.")


app = FastAPI(title="NxtBuild API Gateway", version="1.0.0", lifespan=lifespan)

# CORS configuration - Allow local dev, LAN IPs, and any Vercel domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://([a-zA-Z0-9_\-]+\.)*vercel\.app$|^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)")
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": str(exc.detail)})


async def proxy_request(target_url: str, request: Request) -> Response:
    """Forwards incoming client request to downstream microservice and returns its response."""
    client: httpx.AsyncClient = request.app.state.http_client

    # Forward only clean client headers. Strips Cloudflare and Render edge headers
    # (cf-*, rndr-*, x-forwarded-*) to prevent Cloudflare proxy loop detection (HTTP 429).
    allowed_headers = {"authorization", "content-type", "accept", "user-agent"}
    headers = {k.lower(): v for k, v in request.headers.items() if k.lower() in allowed_headers}

    body = await request.body()

    try:
        upstream_resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.query_params,
            content=body
        )
        try:
            data = upstream_resp.json()
            return JSONResponse(content=data, status_code=upstream_resp.status_code)
        except Exception:
            return Response(
                content=upstream_resp.text,
                status_code=upstream_resp.status_code,
                media_type="text/plain; charset=utf-8"
            )
    except httpx.RequestError as exc:
        logger.error(f"Upstream service connection failed ({target_url}): {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"success": False, "message": "Service temporarily unavailable. Please try again in a moment."}
        )


# --- Global Health Check (Aggregated) ---
@app.get("/api/health")
async def health(request: Request):
    client: httpx.AsyncClient = request.app.state.http_client

    async def check_service(url: str, name: str) -> str:
        try:
            resp = await client.get(f"{url.rstrip('/')}/health", timeout=3.0)
            return "online" if resp.status_code == 200 else "degraded"
        except Exception:
            return "offline"

    auth_status = await check_service(settings.AUTH_SERVICE_URL, "auth")
    proj_status = await check_service(settings.PROJECT_SERVICE_URL, "projects")
    ai_status = await check_service(settings.AI_SERVICE_URL, "ai")

    all_online = all(s == "online" for s in [auth_status, proj_status, ai_status])

    return {
        "success": True,
        "message": "NxtBuild API Gateway is running",
        "services": {
            "gateway": "online",
            "auth_service": auth_status,
            "project_service": proj_status,
            "ai_service": ai_status
        },
        "all_healthy": all_online
    }


# --- Auth Routes -> Proxied to Auth Service ---
@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_auth(path: str, request: Request):
    target_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/{path}"
    return await proxy_request(target_url, request)


# --- AI Generation Route -> Proxied to AI Service ---
@app.post("/api/projects/{id}/generate")
async def route_generate(id: str, request: Request):
    target_url = f"{settings.AI_SERVICE_URL.rstrip('/')}/generate/{id}"
    return await proxy_request(target_url, request)


# --- Project Routes -> Proxied to Project Service ---
@app.api_route("/api/projects", methods=["GET", "POST"])
async def route_projects_root(request: Request):
    target_url = f"{settings.PROJECT_SERVICE_URL.rstrip('/')}/projects"
    return await proxy_request(target_url, request)


@app.api_route("/api/projects/{id}", methods=["GET", "PUT", "DELETE"])
async def route_projects_item(id: str, request: Request):
    target_url = f"{settings.PROJECT_SERVICE_URL.rstrip('/')}/projects/{id}"
    return await proxy_request(target_url, request)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
