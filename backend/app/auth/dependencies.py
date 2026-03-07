from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db.client import supabase

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Validate the JWT from the Authorization header and return the user.

    Supabase's `auth.get_user(token)` verifies the token server-side and
    returns the associated user, which we then pass along as the identity
    for downstream database operations.
    """
    token = credentials.credentials
    try:
        res = supabase.auth.get_user(token)
        user = res.user
        if user is None:
            raise ValueError("No user")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": user.id, "email": user.email}
