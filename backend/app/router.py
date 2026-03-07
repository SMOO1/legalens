from fastapi import APIRouter

from app.routes import documents
from app.auth.router import router as auth_router

router = APIRouter(prefix="/api")

router.include_router(auth_router)
router.include_router(documents.router)
