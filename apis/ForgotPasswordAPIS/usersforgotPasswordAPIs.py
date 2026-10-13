import smtplib
import random
import bcrypt
import os
from fastapi import (HTTPException,status,Response,Cookie,APIRouter)
from jose import jwt, JWTError, ExpiredSignatureError
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from debaggingFile.loggerFile import logger
from dataBase.dataBaseConnectivity import db

router = APIRouter()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not configured")

JWT_ALGORITHM = "HS256"
users_collection = db["usersDetails"]
password_reset_collection  = db["password_reset"]

class verificationEmailRequest(BaseModel):
    email: EmailStr

class UsersVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str


@router.post("/verifycation")
async def verifycation(data: verificationEmailRequest):

    email = data.email.strip().lower()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    try:
        user = users_collection.find_one({
            "userEmail": email
        })
    except Exception:
        logger.exception(
            f"Database error while finding user | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found"
        )

    otp = str(random.randint(100000, 999999))

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(minutes=5)

    password_reset_collection.delete_many({
        "email": email
    })

    try:

        password_reset_collection.insert_one({
            "email": email,
            "otp": otp,
            "jwt_token": None,
            "created_at": now,
            "expires_at": expires_at,
            "verified": False
        })

    except Exception:

        logger.exception(
            f"Failed to save OTP | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create verification code"
        )

    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_APP_PASSWORD")

    if not sender_email or not sender_password:

        password_reset_collection.delete_many({
            "email": email
        })

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service is not configured"
        )

    message = MIMEText(
        f"""
        Hello,
        Your password reset verification code is: {otp}
        This code will expire in 5 minutes.
        If you did not request a password reset, please ignore this email.
        Regards,
        Support Team""")

    message["Subject"] = "Password Reset Verification Code"
    message["From"] = sender_email
    message["To"] = email

    try:

        with smtplib.SMTP("smtp.gmail.com", 587) as server:

            server.starttls()

            server.login(
                sender_email,
                sender_password
            )

            server.send_message(message)

    except Exception:

        logger.exception(
            f"Failed to send OTP email | Email: {email}"
        )

        password_reset_collection.delete_many({
            "email": email
        })

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )

    return {
        "message": "Verification code sent successfully"
    }


@router.post("/usersForgotPassword")
async def usersForgotPassword(data: UsersVerifyOTPRequest,response: Response):

    email = data.email.strip().lower()
    otp = data.otp.strip()

    if not email or not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and OTP are required"
        )

    try:
        verification = password_reset_collection.find_one({
            "email": email,
            "otp": otp,
            "verified": False
        })

    except Exception:
        logger.exception(
            f"Database error while checking OTP | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or OTP"
        )

    expires_at = verification["expires_at"]

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at < datetime.now(timezone.utc):
        password_reset_collection.delete_one({
            "_id": verification["_id"]
        })

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired"
        )

    now = datetime.now(timezone.utc)

    jwt_expires = now + timedelta(minutes=3)

    payload = {
        "email": email,
        "purpose": "user_password_reset",
        "iat": now,
        "exp": jwt_expires
    }

    try:
        reset_token = jwt.encode(
            payload,
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM
        )

    except Exception:
        logger.exception(
            f"Failed to create JWT | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create password reset token"
        )

    try:
        password_reset_collection.update_one(
            {
                "_id": verification["_id"]
            },
            {
                "$set": {
                    "jwt_token": reset_token,
                    "verified": True,
                    "verified_at": now,
                    "jwt_expires_at": jwt_expires
                }
            }
        )

    except Exception:
        logger.exception(
            f"Failed to store JWT | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save password reset token"
        )

    response.set_cookie(
        key="user_password_reset_token",
        value=reset_token,
        max_age=180,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    return {
        "message": "OTP verified successfully",
        "password_reset_allowed": True
    }


@router.post("/resetPassword")
async def resetPassword(data: ResetPasswordRequest,response: Response,user_password_reset_token: str | None = Cookie(default=None)):

    email = data.email.strip().lower()
    new_password = data.new_password

    if not email or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and new password are required"
        )

    if not user_password_reset_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset token is missing"
        )

    try:
        payload = jwt.decode(
            user_password_reset_token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        token_email = payload.get("email")
        token_purpose = payload.get("purpose")

        if token_purpose != "user_password_reset":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password reset token"
            )

        if not token_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password reset token"
            )

        if token_email.lower() != email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email does not match password reset token"
            )

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset token has expired"
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password reset token"
        )

    try:
        verification = password_reset_collection.find_one({
            "email": email,
            "jwt_token": user_password_reset_token,
            "verified": True
        })

    except Exception:
        logger.exception(
            f"Database error while checking reset token | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset session"
        )

    try:
        user = users_collection.find_one({
            "userEmail": email
        })

    except Exception:
        logger.exception(
            f"Database error while finding user | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        hashed_password = bcrypt.hashpw(new_password.encode("utf-8"),bcrypt.gensalt()).decode("utf-8")

    except Exception:
        logger.exception(
            f"Failed to hash password | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to secure password"
        )

    try:
        result = users_collection.update_one(
            {
                "userEmail": email
            },
            {
                "$set": {
                    "password": hashed_password
                }
            }
        )

    except Exception:
        logger.exception(
            f"Database error while updating password | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password could not be updated"
        )

    password_reset_collection.delete_one({"_id": verification["_id"]})

    response.delete_cookie(key="user_password_reset_token")

    logger.info(
        f"Password reset successful | Email: {email}"
    )

    return {
        "message": "Password updated successfully"
    }

