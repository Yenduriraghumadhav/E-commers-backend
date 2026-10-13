from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class VendoreJWTTokenRequest(BaseModel):
    vendore_email: EmailStr
    token: str
    role:Optional[str] = "vendore"
    seller_id: str
    created_at: datetime
