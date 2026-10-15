"""CareSlot - clinic appointment booking API (FastAPI + SQLAlchemy + PostgreSQL)."""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .routers import appointments, doctors

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("careslot")

# Business metric (shown on the Grafana dashboard next to the HTTP metrics).
BOOKINGS = Counter("careslot_appointments_booked_total", "Appointments booked through the API")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # In containers Alembic runs before Uvicorn; create_all is a no-op then and keeps tests self-contained.
    Base.metadata.create_all(bind=engine)
    log.info("%s started env=%s db_host=%s", settings.app_name, settings.app_env, settings.db_host)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan,
              description="Book, reschedule and track patient appointments with clinic doctors.")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "Authorization"])
Instrumentator(excluded_handlers=["/metrics", "/health", "/ready"]).instrument(app).expose(app, endpoint="/metrics")

app.include_router(doctors.router)
app.include_router(appointments.router)


@app.middleware("http")
async def count_bookings(request, call_next):
    response = await call_next(request)
    if request.method == "POST" and request.url.path == "/api/appointments" and response.status_code == 201:
        BOOKINGS.inc()
    return response


@app.get("/", tags=["meta"])
def root():
    return {"service": settings.app_name, "clinic": settings.clinic_name, "version": settings.app_version,
            "env": settings.app_env, "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health():
    """Liveness: the process is up."""
    return {"status": "UP"}


@app.get("/ready", tags=["meta"])
def ready(db: Session = Depends(get_db)):
    """Readiness: the database answers a query."""
    db.execute(text("SELECT 1"))
    return {"status": "READY"}
