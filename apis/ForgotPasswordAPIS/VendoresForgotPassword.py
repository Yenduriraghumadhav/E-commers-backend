from pydantic import EmailStr, BaseModel
import smtplib
from fastapi import Cookie
from jose import jwt, JWTError, ExpiredSignatureError
from dataBase.dataBaseConnectivity import db
from fastapi import HTTPException, status, APIRouter ,Response
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from  schemas.ForgotPasswordSchemas.Forgotpasswordschema import UsersVerifyOTPRequest
import random
import bcrypt
import os
from debaggingFile.loggerFile import logger

router = APIRouter()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not configured")

JWT_ALGORITHM = "HS256"

vendore_collection = db["vendore_collection"]
vendor_password_reset_collection = db["password_reset"]


class vendoreVerificationEmailRequest(BaseModel):
    email: EmailStr

class ForgotPasswordVerificationEmailRequest(BaseModel):
    email: EmailStr
    otp: str

class VendorResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str

@router.post("/vendoreForgotPassword")
def vendoreForgotPassword(data: vendoreVerificationEmailRequest):

    email = data.email.strip().lower()
    if not email:
        logger.warning(f"Email Does not Received | Email: {email}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    try:
        verificationEmail = vendore_collection.find_one({ "vendore_email": email})
    except Exception:
        logger.exception(f"Database error while finding vendor email | Email: {email}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not verificationEmail:
        logger.warning(f"Vendor Email Not Found in DB | Email: {email}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found"
        )

    logger.info(f"Vendor Email found in DB | Email: {email}")

    otp = str(random.randint(100000, 999999))

    logger.info(f"Vendor OTP generated | Email: {email}")

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(minutes=5)

    vendor_password_reset_collection.delete_many({
        "vendore_email": email
    })

    try:
        vendor_password_reset_collection.insert_one({"vendore_email": email,
                                                     "otp": otp,
                                                     "created_at": now,
                                                     "expires_at": expires_at,
                                                     "verified": False
                                                     })

    except Exception:
        logger.exception(f"Failed to save vendor OTP | Email: {email}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create verification code"
        )

    logger.info(f"Vendor OTP saved successfully | Email: {email}")

    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_APP_PASSWORD")

    if not sender_email or not sender_password:
        logger.error("SMTP credentials are not configured")

        vendor_password_reset_collection.delete_many({"email": email})

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service is not configured"
        )

    message = MIMEText(f"""
    Hello,
    Your vendor password reset verification code is: {otp}
    This code will expire in 5 minutes.
    If you did not request a password reset, please ignore this email.
    Regards,
    Support Team"""
    )

    message["Subject"] = "Vendor Password Reset Verification Code"
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
        logger.exception(f"Failed to send vendor OTP email | Email: {email}")

        vendor_password_reset_collection.delete_many({"email": email})

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )
    logger.info(f"Vendor verification email sent successfully | Email: {email}")

    return {
        "message": "Verification code sent successfully"
    }


@router.post("/vendorOtp")
def vendorOtp(data: ForgotPasswordVerificationEmailRequest,response: Response):

    email = data.email.strip().lower()
    otp = data.otp.strip()

    if not email or not otp:
        logger.warning(
            f"Vendor Email or OTP missing | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and OTP are required"
        )

    try:
        verification = vendor_password_reset_collection.find_one({
            "vendore_email": email,
            "otp": otp,
            "verified": False
        })

    except Exception:
        logger.exception(
            f"Database error while finding vendor OTP | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not verification:
        logger.warning(
            f"Invalid vendor email or OTP | Email: {email}"
        )

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
        logger.warning(
            f"Vendor OTP expired | Email: {email}"
        )
        vendor_password_reset_collection.delete_one({"_id": verification["_id"]})

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired"
        )

    now = datetime.now(timezone.utc)

    jwt_expires = now + timedelta(minutes=3)

    token_payload = {
        "vendore_email": email,
        "purpose": "vendor_password_reset",
        "iat": now,
        "exp": jwt_expires
    }

    try:
        reset_token = jwt.encode(
            token_payload,
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM
        )

    except Exception:
        logger.exception(
            f"Failed to create vendor reset JWT | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create password reset token"
        )

    try:
        vendor_password_reset_collection.update_one(
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
            f"Failed to save vendor JWT | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save password reset token"
        )

    response.set_cookie(
        key="vendor_password_reset_token",
        value=reset_token,
        max_age=180,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    logger.info(
        f"Vendor email and OTP verified successfully | Email: {email}"
    )

    return {
        "message": "OTP verified successfully",
        "password_reset_allowed": True
    }


@router.post("/vendorResetPassword")
def vendorResetPassword(data: VendorResetPasswordRequest, response: Response,vendor_password_reset_token: str | None = Cookie(default=None)):

    email = data.email.strip().lower()
    new_password = data.new_password

    if not email or not new_password:

        logger.warning(
            f"Vendor email or new password missing | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and new password are required"
        )

    if not vendor_password_reset_token:

        logger.warning(
            f"Vendor reset JWT missing | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset token is missing"
        )

    try:
        payload = jwt.decode(
            vendor_password_reset_token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        token_email = payload.get("vendore_email")

        token_purpose = payload.get("purpose")

        logger.info(
            f"Vendor reset JWT decoded | "
            f"Token Email: {token_email}"
        )

        if token_purpose != "vendor_password_reset":

            logger.warning(
                f"Invalid vendor JWT purpose | Email: {email}"
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password reset token"
            )

        if not token_email:

            logger.warning(
                f"Email missing from vendor JWT | Email: {email}"
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password reset token"
            )

        if token_email.strip().lower() != email:

            logger.warning(
                f"JWT email mismatch | "
                f"Request Email: {email} | "
                f"Token Email: {token_email}"
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email does not match password reset token"
            )

    except ExpiredSignatureError:
        logger.warning(
            f"Vendor reset JWT expired | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset token has expired"
        )

    except JWTError:
        logger.warning(
            f"Invalid vendor reset JWT | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password reset token"
        )

    try:
        verification = vendor_password_reset_collection.find_one(
            {
                "vendore_email": email,
                "jwt_token": vendor_password_reset_token,
                "verified": True
            }
        )

    except Exception:
        logger.exception(
            f"Database error while checking vendor reset token | "
            f"Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not verification:
        logger.warning(
            f"Vendor email or JWT not found in password reset DB | "
            f"Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset session"
        )

    jwt_expires_at = verification.get("jwt_expires_at")

    if jwt_expires_at:

        if jwt_expires_at.tzinfo is None:

            jwt_expires_at = jwt_expires_at.replace(
                tzinfo=timezone.utc
            )

        if jwt_expires_at < datetime.now(timezone.utc):

            logger.warning(
                f"Vendor reset session expired | Email: {email}"
            )

            vendor_password_reset_collection.delete_one(
                {
                    "_id": verification["_id"]
                }
            )

            response.delete_cookie(
                key="vendor_password_reset_token"
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password reset session has expired"
            )

    try:
        vendor = vendore_collection.find_one(
            {
                "vendore_email": email
            }
        )

    except Exception:
        logger.exception(
            f"Database error while finding vendor | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if not vendor:
        logger.warning(
            f"Vendor not found | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )

    try:
        hashed_password = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

    except Exception:
        logger.exception(
            f"Failed to hash vendor password | Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to secure password"
        )

    try:
        result = vendore_collection.update_one(
            {
                "vendore_email": email
            },
            {
                "$set": {
                    "vendore_password": hashed_password
                }
            }
        )

    except Exception:
        logger.exception(
            f"Database error while updating vendor password | "
            f"Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    if result.matched_count == 0:
        logger.warning(
            f"Vendor not found while resetting password | "
            f"Email: {email}"
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )

    try:
        vendor_password_reset_collection.delete_one(
            {
                "_id": verification["_id"]
            }
        )

    except Exception:
        logger.exception(
            f"Failed to delete vendor reset record | "
            f"Email: {email}"
        )

    response.delete_cookie(
        key="vendor_password_reset_token"
    )

    logger.info(
        f"Vendor password reset successful | Email: {email}"
    )

    return {
        "message": "Password updated successfully"
    }

