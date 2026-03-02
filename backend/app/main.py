"""
TransferSimple — FastAPI application entry point.

Start with:
    cd TransferSimple/backend
    uvicorn app.main:app --reload --port 8000
"""
# Import config first — sets proxy env vars before any HTTP clients initialise
import app.config  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes    import router as api_router
from app.api.websocket import router as ws_router

app = FastAPI(
    title="TransferSimple",
    description="AI-powered ATON transfer resolution platform",
    version="0.1.0",
)

# ── CORS — allow the Vite dev server (port 5173) ──────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"service": "TransferSimple backend", "docs": "/docs"}
