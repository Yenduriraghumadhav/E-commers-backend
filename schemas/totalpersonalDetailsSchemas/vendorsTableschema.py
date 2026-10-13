from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional


class VendorSchema(BaseModel):
    vendore_name: str
    vendore_email: EmailStr
    vendore_mobileNumber: str
    vendore_country: str
    vendore_address: str
    vendore_pincode: str
    vendore_password: str
    vendore_Renter_Password: str
    seller_id : str
    images: Optional[str] = None
    role: Optional[str] = "vendore"

    @model_validator(mode="after")
    def check_password(self):
        if self.vendore_password != self.vendore_Renter_Password:
            raise ValueError("Passwords do not match")

        return self
