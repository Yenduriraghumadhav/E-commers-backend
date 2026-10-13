from pydantic import BaseModel, EmailStr

class UsersVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    jwt_token : str
