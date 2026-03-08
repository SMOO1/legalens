import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.router import router

# Use INFO by default so DEBUG logs (e.g. httpx, httpcore, PDF content) don't flood the console
logging.basicConfig(level=logging.INFO)
for name in ("httpx", "httpcore", "python_multipart"):
    logging.getLogger(name).setLevel(logging.WARNING)

app = FastAPI(title="LegaLens API")

# CORS: allow local dev + production. On Google Cloud Run set CORS_ORIGINS to your frontend URL(s).
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").strip()
allow_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "LegaLens API"}

