from fastapi import APIRouter, Depends, HTTPException, status
from gotrue.errors import AuthApiError

from db.client import supabase
from app.auth.schemas import (
    SignUpRequest,
    SignInRequest,
    TokenResponse,
    RefreshRequest,
    UserOut,
)
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def sign_up(body: SignUpRequest):
    try:
        res = supabase.auth.sign_up({"email": body.email, "password": body.password})
    except AuthApiError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    session = res.session
    if session is None:
        # Email confirmation required – no session yet
        return HTTPException(
            status_code=status.HTTP_200_OK,
            detail="Check your email to confirm your account",
        )

    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=res.user.id,
        email=res.user.email,
    )


@router.post("/signin", response_model=TokenResponse)
async def sign_in(body: SignInRequest):
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except AuthApiError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return TokenResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        user_id=res.user.id,
        email=res.user.email,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    try:
        res = supabase.auth.refresh_session(body.refresh_token)
    except AuthApiError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return TokenResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        user_id=res.user.id,
        email=res.user.email,
    )


@router.post("/signout")
async def sign_out(user: dict = Depends(get_current_user)):
    supabase.auth.sign_out()
    return {"message": "Signed out successfully"}


@router.get("/me", response_model=UserOut)
async def get_me(user: dict = Depends(get_current_user)):
    return UserOut(user_id=user["user_id"], email=user["email"])
