import asyncio
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
    """Forwards incoming client request to downstream microservice with automatic retry for cold starts."""
    client: httpx.AsyncClient = request.app.state.http_client

    # Forward only clean client headers. Strips Cloudflare and Render edge headers
    # (cf-*, rndr-*, x-forwarded-*) to prevent Cloudflare proxy loop detection.
    allowed_headers = {"authorization", "content-type", "accept", "user-agent"}
    headers = {k.lower(): v for k, v in request.headers.items() if k.lower() in allowed_headers}

    body = await request.body()

    # Retry strategy for Render free-tier cold-starts:
    # When downstream is asleep, Render edge returns 429 / 502 / 503 / 504 while container boots (~15-25s)
    max_retries = 4
    retry_delays = [2.0, 3.5, 5.0]
    last_error = None

    for attempt in range(max_retries):
        try:
            upstream_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body
            )

            # Check if Render edge returned a transient cold-boot code (e.g. 429 rate limit or 502/503 during boot)
            if upstream_resp.status_code in {429, 502, 503, 504} and attempt < len(retry_delays):
                delay = retry_delays[attempt]
                logger.warning(
                    f"Upstream {target_url} returned {upstream_resp.status_code} (cold-start / spin-up). "
                    f"Retrying in {delay}s (attempt {attempt + 1}/{max_retries})..."
                )
                await asyncio.sleep(delay)
                continue

            # Attempt to parse upstream JSON response
            try:
                data = upstream_resp.json()
                return JSONResponse(content=data, status_code=upstream_resp.status_code)
            except Exception:
                # If upstream returned a non-JSON 429 after all retries, never expose raw 429 to client.
                # Transform it into a graceful 503 with friendly JSON message for the frontend.
                if upstream_resp.status_code == 429:
                    return JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={
                            "success": False,
                            "message": "Services are waking up from sleep mode. Please wait a moment and try again."
                        }
                    )
                return Response(
                    content=upstream_resp.text,
                    status_code=upstream_resp.status_code,
                    media_type="text/plain; charset=utf-8"
                )

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < len(retry_delays):
                delay = retry_delays[attempt]
                logger.warning(
                    f"Upstream {target_url} connection error: {exc}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                continue
            break

    logger.error(f"Upstream service connection failed after {max_retries} attempts ({target_url}): {last_error}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "success": False,
            "message": "Services are waking up from sleep mode. Please wait a few seconds and try again."
        }
    )


# --- Global Health Check (Aggregated & Parallel Pre-Warming) ---
@app.get("/api/health")
async def health(request: Request):
    client: httpx.AsyncClient = request.app.state.http_client

    async def ping_service(url: str, name: str) -> tuple[str, str]:
        try:
            resp = await client.get(f"{url.rstrip('/')}/health", timeout=10.0)
            return name, "online" if resp.status_code == 200 else "degraded"
        except Exception:
            return name, "offline"

    # Ping all 3 downstream services concurrently in parallel to pre-warm containers
    results = await asyncio.gather(
        ping_service(settings.AUTH_SERVICE_URL, "auth_service"),
        ping_service(settings.PROJECT_SERVICE_URL, "project_service"),
        ping_service(settings.AI_SERVICE_URL, "ai_service"),
        return_exceptions=True
    )

    services_status = {"gateway": "online"}
    for res in results:
        if isinstance(res, tuple):
            services_status[res[0]] = res[1]

    all_online = all(status == "online" for status in services_status.values())

    return {
        "success": True,
        "message": "NxtBuild API Gateway is running",
        "services": services_status,
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
