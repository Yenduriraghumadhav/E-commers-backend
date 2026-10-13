from typing import Optional

from pydantic import BaseModel, model_validator


class UserSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    userEmail: Optional[str] = None
    password: Optional[str] = None
    country : Optional[str] = None
    Renter_Password: Optional[str] = None
    role : Optional[str] = "user"
    Gender : str


    step: str
    otp: str | None = None

    @model_validator(mode="after")
    def check_password(self):
        if self.password != self.Renter_Password:
            raise ValueError("Passwords do not match")
        return self