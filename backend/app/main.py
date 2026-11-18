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
    # Startup: ensure live demo auction is active on every startup
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
app.include_router(rfqs.router, prefix="/api/v1")
app.include_router(bids.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(ws.router)

