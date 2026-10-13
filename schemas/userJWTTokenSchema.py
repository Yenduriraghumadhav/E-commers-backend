from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserJWTTokenRequest(BaseModel):
    user_email: EmailStr
    token: str
    role: Optional[str] = "user"
    created_at: datetime
