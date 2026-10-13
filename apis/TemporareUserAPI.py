from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from email.message import EmailMessage
import os
import random
import smtplib
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi import ( APIRouter, HTTPException, Response, status)
from jose import jwt
from debaggingFile.loggerFile import logger
from dataBase.dataBaseConnectivity import db
from pymongo import ASCENDING


router = APIRouter()

Athentications = db["AthenticationPerpose"]
load_dotenv()

Athentications.create_index( [("expires_at", ASCENDING)], expireAfterSeconds=0 )

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

ALGORITHM = "HS256"


class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


@router.post("/login/send-otp")
async def send_otp(data: SendOTPRequest):

    email = data.email.lower().strip()

    if not email:
        logger.info(
            "Email address not provided"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or OTP"
        )

    otp = f"{random.randint(0, 999999):06d}"

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    Athentications.insert_one({
        "email": email,
        "otp_hash": otp,
        "expires_at": expires_at
    })

    logger.info(
        "past data of otp inserted to DB",
    )

    message = EmailMessage()

    message["From"] = SMTP_EMAIL
    message["To"] = email
    message["Subject"] = "Your Login OTP"

    message.set_content(
        f"""
        Your OTP is: {otp}
        This OTP is valid for 5 minutes.
        Do not share this OTP with anyone.""")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as server:
            server.login(
                SMTP_EMAIL,
                SMTP_APP_PASSWORD
            )

            server.send_message(message)

            logger.info(
                "otp send successfully",
            )

    except Exception as e:
        logger.error(
            f"Failed to send OTP email: {e}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

    return {
        "message": "OTP sent successfully"
    }


@router.post("/login/verify-otp")
async def verify_otp(data: VerifyOTPRequest, response: Response):

    email = data.email.lower().strip()
    otp = data.otp.strip()

    logger.info(f"frontend email {email}")
    logger.info(f"frontend otp {otp}")


    if not email or not otp:
        logger.error("Email or OTP not provided")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or OTP"
        )

    otp_record = Athentications.find_one({
        "email": email,
        "otp_hash": otp
    })

    if not otp_record:
        logger.error(
            f"Invalid email or OTP | email={email}"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or OTP"
        )

    now = datetime.now(timezone.utc)

    expires_at_from_db = otp_record["expires_at"]

    if expires_at_from_db.tzinfo is None:
        expires_at_from_db = expires_at_from_db.replace(
            tzinfo=timezone.utc
        )

    if expires_at_from_db < now:
        logger.info(
            f"OTP expired | email={email}"
        )

        Athentications.delete_one({"_id": otp_record["_id"]})

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP expired"
        )

    Athentications.delete_one({"_id": otp_record["_id"]})

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=20)

    payload = {
        "email": email,
        "exp": expires_at
    }

    access_token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=ALGORITHM
    )

    Athentications.insert_one({
        "email": email,
        "token": access_token,
        "expires_at": expires_at
    })

    response.set_cookie(
        key="vendor_access_token",
        value=access_token,
        max_age=15 * 60,
        expires=15 * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    logger.info(
        f"Email verified and token generated | email={email}"
    )

    return {
        "message": "Login successful",
        "userEmail" : email
    }







