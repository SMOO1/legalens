from pydantic import BaseModel


class UserOut(BaseModel):
    user_id: str
    email: str
