"""
SchoolBrain.ai — Main FastAPI Application
Run: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

from routers import chat, students, quiz, plans, analytics, auth, reports, admin, memory_routes
from models.schemas import HealthResponse
from database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SchoolBrain.ai API",
    description="AI platform for schools — weak student detection, quiz generation, intervention plans",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router,           prefix="/auth",       tags=["Auth"])
app.include_router(chat.router,           prefix="",            tags=["Chat"])
app.include_router(students.router,       prefix="/students",   tags=["Students"])
app.include_router(quiz.router,           prefix="/quiz",       tags=["Quiz"])
app.include_router(plans.router,          prefix="",            tags=["Plans"])
app.include_router(analytics.router,      prefix="/analytics",  tags=["Analytics"])
app.include_router(reports.router,        prefix="/reports",    tags=["Reports"])
app.include_router(memory_routes.router,  prefix="/memory",     tags=["Memory"])
app.include_router(admin.router,          prefix="/admin",      tags=["Admin"])

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("SchoolBrain API starting up...")
    init_db()
    logger.info("Database initialised.")

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(status="ok", version="1.0.0", timestamp=datetime.utcnow().isoformat())

# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": str(exc), "status": 500})
