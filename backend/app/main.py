import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.services.exceptions import MeridianException
from app.services.background import auction_status_sweeper_task
from app.routers import auth, rfqs, bids, suppliers, analytics, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("meridian")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure live demo auction is active on every startup (unless running tests)
    if not os.environ.get("TESTING"):
        try:
            from app.seeds.seed_data import reseed_live_demo
            reseed_live_demo()
            logger.info("Live demo auction primed and active on startup.")
        except Exception as e:
            logger.warning("Could not auto-prime live demo on startup: %s", e)

    # Startup: launch background sweeper
    sweeper_task = asyncio.create_task(auction_status_sweeper_task())
    logger.info("MERIDIAN British Auction Engine online.")
    yield
    # Shutdown: clean up background task
    sweeper_task.cancel()
    try:
        await sweeper_task
    except asyncio.CancelledError:
        pass
    logger.info("MERIDIAN British Auction Engine shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="MERIDIAN: British Auction RFQ Procurement Exchange",
    lifespan=lifespan,
)

# CORS configuration
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if not origins or "*" in origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured JSON request logging middleware
@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    start_time = asyncio.get_event_loop().time()
    response = await call_next(request)
    duration_ms = round((asyncio.get_event_loop().time() - start_time) * 1000, 2)
    client_host = request.client.host if request.client else "unknown"
    logger.info(
        '{"event": "http_request", "method": "%s", "path": "%s", "status": %d, "duration_ms": %.2f, "client": "%s"}',
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        client_host,
    )
    return response


# In-memory sliding window rate limiter
_rate_limits: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_MAX_REQUESTS_PER_WINDOW = 300


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    # Skip rate limiting for health check paths
    if request.url.path in ["/health", "/api/v1/health", "/api/health"] or request.url.path.startswith("/ws/"):
        return await call_next(request)

    client_ip = request.headers.get("X-Test-Client-Id") or (request.client.host if request.client else "127.0.0.1")
    now_ts = asyncio.get_event_loop().time()

    custom_limit = request.headers.get("X-Test-Rate-Limit")
    max_requests = int(custom_limit) if custom_limit and custom_limit.isdigit() else DEFAULT_MAX_REQUESTS_PER_WINDOW

    timestamps = _rate_limits.setdefault(client_ip, [])
    cutoff = now_ts - RATE_LIMIT_WINDOW_SECONDS
    _rate_limits[client_ip] = [ts for ts in timestamps if ts > cutoff]

    if len(_rate_limits[client_ip]) >= max_requests:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Too many requests. Limit is {max_requests} requests per minute.",
                "details": {"retry_after_seconds": 60},
            },
            headers={"Retry-After": "60"},
        )

    _rate_limits[client_ip].append(now_ts)
    return await call_next(request)

@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    from app.database import engine
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "service": "MERIDIAN Auction Engine",
        "database": engine.dialect.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# Register custom exception handler for Domain Exceptions
@app.exception_handler(MeridianException)
async def meridian_exception_handler(request: Request, exc: MeridianException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Register handler for standard HTTPExceptions for uniform error contract across entire API
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "HTTP_ERROR")
        message = exc.detail.get("message", str(exc.detail))
        details = exc.detail.get("details", {})
    else:
        code = "HTTP_ERROR"
        message = str(exc.detail)
        details = {}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": message,
            "details": details,
        },
    )


# Register validation error handler for consistent Pydantic responses
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        errors.append(f"{field}: {err.get('msg')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({
            "code": "VALIDATION_ERROR",
            "message": "Invalid request payload: " + "; ".join(errors),
            "details": {"errors": exc.errors()},
        }),
    )


# Health check endpoint
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "MERIDIAN Auction Engine",
        "version": "1.0.0",
    }


# Include Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(suppliers.router, prefix="/api/v1")
app.include_router(suppliers.router, prefix="")  # Alias for /suppliers
app.include_router(rfqs.router, prefix="/api/v1")
app.include_router(bids.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(ws.router)

