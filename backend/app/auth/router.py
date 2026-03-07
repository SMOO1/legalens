from fastapi import APIRouter, Depends

from app.auth.schemas import UserOut
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
async def get_me(user: dict = Depends(get_current_user)):
    return UserOut(user_id=user["user_id"], email=user["email"])
