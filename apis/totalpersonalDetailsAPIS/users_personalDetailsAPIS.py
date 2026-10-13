from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import os
import re
import smtplib
from random import randint
import phonenumbers
from fastapi import HTTPException, Response, status , Cookie
from fastapi import APIRouter
from schemas.totalpersonalDetailsSchemas.usersTableSchema import UserSchema
from dataBase.dataBaseConnectivity import db
from debaggingFile.loggerFile import logger
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")

router = APIRouter()

users_collection = db["usersDetails"]
user_JWTToken = db["Userslogin_history"]
otpcheking = db["userGenarationOTPforuserEmail"]
SECRET_KEY = "SRZvCv02LqEjQofXk4LBN6THYaWW9S_3PRCH2LE1dqJJfXF6fFvc0mVlRabgeWhx"
Algoritham_code = "HS256"


def send_otp_email(receiver_email: str, otp: str):
    try:
        message = MIMEMultipart()
        message["From"] = SMTP_EMAIL
        message["To"] = receiver_email
        message["Subject"] = "Email Verification OTP"

        body = f"""
Hello,

Your OTP for email verification is:

{otp}

This OTP is valid for 5 minutes.

If you did not request this OTP, please ignore this email.

Regards,
E-Commerce Team
"""

        message.attach(
            MIMEText(body, "plain")
        )

        with smtplib.SMTP(
            "smtp.gmail.com",
            587
        ) as server:

            server.starttls()
            server.login(
                SMTP_EMAIL,
                SMTP_APP_PASSWORD
            )
            server.sendmail(
                SMTP_EMAIL,
                receiver_email,
                message.as_string()
            )
        logger.info(
            f"OTP email sent successfully | email={receiver_email}"
        )
    except Exception:
        logger.exception(
            f"Failed to send OTP email | email={receiver_email}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to send OTP email"
        )

@router.post("/usersDetails")
def usersDetailsPost(user: UserSchema, response: Response):

    email = user.userEmail.strip().lower()

    if not email:
        logger.warning(
            "Email was not provided"
        )
        raise HTTPException(
            status_code=400,
            detail="Email is required"
        )

    if user.step == "send_otp":
        existingUser = users_collection.find_one({"userEmail": email})

        if existingUser:
            logger.warning(
                f"Email already registered | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        otp = str(
            randint(
                100000,
                999999
            )
        )

        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=5)
        otpcheking.delete_many({
            "userEmail": email
        })

        otpcheking.insert_one({
            "userEmail": email,
            "otp": otp,
            "created_at": now,
            "expires_at": expire,
            "verified": False
        })

        logger.info(
            f"OTP generated and saved | email={email}"
        )

        send_otp_email(email,otp)

        logger.info(
            f"OTP sent successfully | email={email}"
        )

        return {
            "message": "OTP sent successfully",
            "userEmail": email
        }

    if user.step == "verify_otp":
        if not user.otp:
            logger.warning(
                f"OTP was not provided | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail="OTP is required"
            )

        otpData = otpcheking.find_one({
            "userEmail": email,
            "otp": user.otp,
            "verified": False
        })

        if not otpData:
            logger.warning(
                f"Invalid OTP | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid OTP"
            )

        now = datetime.now(timezone.utc)
        expires_at = otpData["expires_at"]

        if expires_at.tzinfo is None:expires_at = expires_at.replace( tzinfo=timezone.utc)
        if now > expires_at:
            logger.warning(
                f"OTP expired | email={email}"
            )

            otpcheking.delete_one({"_id": otpData["_id"]})

            raise HTTPException(
                status_code=400,
                detail="OTP expired"
            )

        logger.info(
            f"OTP expiry validation successful | email={email}"
        )

        if (
            not user.first_name.strip()
            or not user.last_name.strip()
            or not user.address.strip()
            or not user.phone_number.strip()
            or not user.pincode.strip()
            or not user.password.strip()
            or not user.Renter_Password.strip()
            or not user.userEmail.strip()
            or not user.Gender.strip()
        ):
            logger.info(
                "Validation failed, missing required fields"
            )
            raise HTTPException(
                status_code=400,
                detail="Validation failed. Missing required fields."
            )

        try:
            phone = phonenumbers.parse(user.phone_number,user.country)
        except Exception:
            logger.warning(
                f"Invalid phone number format | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number"
            )

        if not phonenumbers.is_valid_number(phone):
            logger.warning(
                f"Invalid phone number | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number"
            )

        password_pattern = (
            r"^(?=.*[A-Za-z])"
            r"(?=.*\d)"
            r"(?=.*[^A-Za-z0-9])"
            r".{8,}$"
        )

        if not re.match(password_pattern,user.password ):
            logger.warning(
                f"Invalid password format | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Password must contain 8 characters, "
                    "and contain alphabets, numbers, "
                    "and a special symbol"
                )
            )

        if user.password != user.Renter_Password:
            logger.warning(
                f"Passwords do not match | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail="Passwords do not match"
            )

        existingUser = users_collection.find_one({ "userEmail": email})

        if existingUser:
            logger.warning(
                f"Email already registered | email={email}"
            )
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        users_data = user.model_dump()
        users_data.pop("Renter_Password",None)
        users_data.pop( "step",None)
        users_data.pop("otp",None)
        users_data["role"] = "user"
        users_data["userEmail"] = email
        hashed_password = bcrypt.hashpw(
            users_data["password"].encode(
                "utf-8"
            ),
            bcrypt.gensalt()
        )

        users_data["password"] = (
            hashed_password.decode(
                "utf-8"
            )
        )

        try:
            result = users_collection.insert_one(users_data)

            logger.info(
                f"User created successfully | "
                f"email={email} | "
                f"user_id={result.inserted_id}"
            )

        except Exception:
            logger.exception(
                f"Database error while creating user | "
                f"email={email}"
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )

        otpcheking.update_one(
            {
                "_id": otpData["_id"]
            },
            {
                "$set": {
                    "verified": True,
                    "verified_at": now
                }
            }
        )

        logger.info(
            f"Email verified successfully | email={email}"
        )

        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=15)

        payload = {
            "userEmail": email,
            "role": "user",
            "type": "access",
            "exp": expire
        }

        logger.info(
            f"JWT payload created | email={email}"
        )

        token = jwt.encode(
            payload,
            SECRET_KEY,
            algorithm=Algoritham_code
        )

        try:
            user_JWTToken.insert_one({
                "userEmail": email,
                "token": token,
                "created_at": now,
                "expires_at": expire
            })

            user_JWTToken.create_index("expires_at",expireAfterSeconds=0)

            logger.info(
                f"JWT saved successfully | email={email}"
            )

        except Exception:
            logger.exception(
                f"Database error while saving JWT | "
                f"email={email}"
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )

        otpcheking.delete_one({"_id": otpData["_id"]})

        logger.info(
            f"Verified OTP deleted | email={email}"
        )

        response.set_cookie(
            key="jwt_Token",
            value=token,
            max_age=15 * 60,
            httponly=True,
            secure=True,
            samesite="lax"
        )

        response.set_cookie(
            key="user_email",
            value=email,
            max_age=15 * 60,
            httponly=True,
            secure=True,
            samesite="lax"
        )

        logger.info(
            f"Cookies sent successfully | email={email}"
        )

        return {
            "message": "Registration successful",
            "userEmail": email,
            "role": "user"
        }
    raise HTTPException(
        status_code=400,
        detail="Invalid step. Use 'send_otp' or 'verify_otp'."
    )


@router.put("/usersDetails")
def usersDetailsPut(userEmail: str,user: UserSchema,user_jwttoken: str | None = Cookie(default=None)):

    if not userEmail:
        raise HTTPException(
            status_code=400,
            detail="Email not provided"
        )

    if not user_jwttoken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token not provided"
        )

    token_data = user_JWTToken.find_one({
        "user_email": userEmail,
        "token": user_jwttoken
    })

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token or unauthorized user"
        )

    existing_user = users_collection.find_one(
        {"userEmail": userEmail}
    )

    if existing_user is None:
        raise HTTPException(
            status_code=404,
            detail="User with this email not found"
        )

    update_data = user.model_dump(
        exclude_unset=True
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update"
        )

    users_collection.update_one(
        {"userEmail": userEmail},
        {"$set": update_data}
    )

    return {
        "message": "User updated successfully",
        "updated_fields": list(update_data.keys())
    }


@router.get("/usersDetails")
def usersDetailsget( userEmail: str, jwt_Token: str | None = Cookie(default=None)):

    if not jwt_Token:
        logger.error(
            "JWT Token Required"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT Token Required"
        )

    if not userEmail:
        logger.error(
            "User Email Required"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User Email Required"
        )

    verification = user_JWTToken.find_one({
        "userEmail": userEmail,
        "token": jwt_Token
    })

    if not verification:
        logger.error(
            f"JWT verification failed | email={userEmail}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Email or JWT Token"
        )

    user_details = users_collection.find_one(
        {
            "userEmail": userEmail
        },
        {
            "_id": 0,
            "first_name": 1,
            "last_name": 1,
            "phone_number": 1,
            "userEmail": 1,
            "address": 1,
            "pincode":1
        }
    )

    if not user_details:
        logger.warning(
            f"User details not found | email={userEmail}"
        )
        return {
            "message": "User not found"
        }

    return {
        "details": user_details
    }


@router.delete("/usersDetails")
def usersDetailsDelete(userEmail: str ,jwt_Token: str | None = Cookie(default=None)):

    if not userEmail:
        logger.info(
            "User Email Required"
        )
        raise HTTPException(
            status_code=400,
            detail="Email not provided"
        )

    if not jwt_Token:
        logger.error(
            "JWT Token Required"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT Token not provided"
        )

    chekingToken = user_JWTToken.find_one({"token": jwt_Token})

    if not chekingToken:
        logger.error(
            f"JWT Verification failed | token={jwt_Token}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT Token"
        )

    users_collection.delete_one({"userEmail": userEmail})
    return {
        "message": "User deleted successfully",
        "user_id": str(users_collection.count_documents({"userEmail": userEmail}))
    }
