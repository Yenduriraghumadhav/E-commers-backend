from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class LoginHistorySchema(BaseModel):
    Email: EmailStr
    role: str
    jit : str
    login_time: datetime
    logout_time: Optional[datetime] = None
    token : Optional[str] = None