import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

sys.path.insert(0, os.path.dirname(__file__))

from admin_routes import router as admin_router
from auth_routes import router as auth_router
from chatbot_routes import router as chatbot_router
from database import Base, engine
from payment_routes import router as payment_router
from policy_routes import router as policy_router
from worker_routes import router as worker_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_startup_migrations()
    logger.info("Database schema checked and ready")
    yield


app = FastAPI(
    title="SafeFlow.ai API",
    description="Parametric micro-insurance for gig workers in India",
    version="3.1.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]
allow_credentials = "*" not in allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["http://localhost:3000"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error for %s %s", request.method, request.url.path)
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info("%s %s -> %s in %sms", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


app.include_router(auth_router)
app.include_router(worker_router)
app.include_router(admin_router)
app.include_router(policy_router)
app.include_router(chatbot_router)
app.include_router(payment_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "SafeFlow.ai", "version": "3.1.0"}


@app.get("/api/public-config")
def public_config():
    return {
        "firebase": {
            "apiKey": os.getenv("FIREBASE_API_KEY", "").strip(),
            "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", "").strip(),
            "projectId": os.getenv("FIREBASE_PROJECT_ID", "").strip(),
            "appId": os.getenv("FIREBASE_APP_ID", "").strip(),
            "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", "").strip(),
        }
    }


def _run_startup_migrations():
    inspector = inspect(engine)

    if inspector.has_table("workers"):
        worker_columns = {column["name"] for column in inspector.get_columns("workers")}
        if "firebase_uid" not in worker_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE workers ADD COLUMN firebase_uid VARCHAR"))

    # Re-run create_all in case newer ORM tables do not exist yet.
    Base.metadata.create_all(bind=engine)


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.join(os.getcwd(), "frontend")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info("Frontend served from: %s", frontend_dir)
else:
    logger.warning("Frontend directory not found - API-only mode")
