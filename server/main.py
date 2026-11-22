import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.api.routes import auth, health, projects
from app.core.config import settings
from app.core.database import close_database_connection, connect_to_database
from app.middleware.observability import ObservabilityMiddleware

# Configure structured application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nxtbuild")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown events.
    Verifies database connectivity, logs configuration, and handles cleanup.
    """
    logger.info("Starting NxtBuild FastAPI server...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"CORS Allowed Origins: {settings.cors_origins}")

    if not settings.JWT_SECRET:
        logger.error("JWT_SECRET is missing! Please configure it in your .env file.")

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Page generation calls will fail.")

    try:
        await connect_to_database()
    except Exception as exc:
        logger.error(f"Failed to connect to MongoDB on startup: {exc}")
        # Server can still start for diagnostics or retry, but log clearly

    yield

    logger.info("Shutting down NxtBuild server...")
    await close_database_connection()


app = FastAPI(
    title="NxtBuild API",
    description="Scalable, asynchronous backend for the NxtBuild AI website builder",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 1. Observability middleware (logs latency and paths)
app.add_middleware(ObservabilityMiddleware)

# 2. CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://([a-zA-Z0-9_\-]+\.)*vercel\.app$|^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 3. Global exception handlers ensuring 100% frontend contract compatibility
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Formats all HTTP exceptions to match frontend { success: false, message: ... } format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Extracts first validation issue into a clean, human-readable error message."""
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    field = first_error.get("loc", ["field"])[-1]
    msg = first_error.get("msg", "Invalid value")
    readable_message = f"Invalid {field}: {msg}"

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "message": readable_message
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "success": False,
            "message": f"Endpoint not found: {request.url.path}"
        }
    )


# 4. Route registration under /api prefix
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        access_log=False  # Handled by custom observability middleware
    )
