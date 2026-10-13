import email
from calendar import Day

from debaggingFile.loggerFile import logger
logger.info("🔥 USER LOGIN MODULE LOADED")
import uuid
from datetime import datetime, timedelta, timezone
from pydantic import  BaseModel
import bcrypt
import jwt
from fastapi import APIRouter, Response, Cookie, HTTPException

from dataBase.dataBaseConnectivity import db

user_collection = db["usersDetails"]
loginInfo_collection = db["Userslogin_history"]

router = APIRouter()
SECRET_KEY = "userDetails@123_of_ecommersProdect@12334#@#!@#$4321"
ALGORITHM = "HS256"

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/usersLogin")
def usersLoginChecking(data: LoginRequest, response: Response):

    email = data.email.strip()
    password = data.password

    logger.info(f"Login attempt started | email={email}")

    if not email:
        logger.warning("Login failed | Email was not provided")

        raise HTTPException(
            status_code=401,
            detail="Email is required"
        )

    try:
        user = user_collection.find_one({"userEmail": email})
    except Exception:
        logger.exception(f"Database error while finding user | email={email}")

        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

    if user is None:
        logger.warning(f"Login failed | User not found | email={email}")

        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    stored_password = user["password"]

    if not bcrypt.checkpw(password.encode("utf-8"),stored_password.encode("utf-8")):
        logger.warning(f"Login failed | Incorrect password | email={email}")

        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    logger.info(f"Password verification successful | email={email}")

    role = user.get("role", "user")

    now = datetime.now(timezone.utc)

    expire = now + timedelta(minutes=15)

    payload = {
        "userEmail": email,
        "role": role,
        "type": "access",
        "exp": expire
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    logger.debug(f"Vendor JWT generated | email={email}")

    try:
        loginInfo_collection.insert_one({
            "userEmail": email,
            "token": token,
            "created_at": now,
            "expires_at": expire
        })

        loginInfo_collection.create_index(
            "expires_at",
            expireAfterSeconds=0
        )

        logger.info(
            "Login successful | email={email}".format(email=email)
        )
    except:
        logger.exception(f"Database error while finding user | email={email}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
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
    logger.info(f"Login successful | email={email}")

    return {
        "message": "Login successful",
        "userEmail" : email,
        "role" : role,
    }
