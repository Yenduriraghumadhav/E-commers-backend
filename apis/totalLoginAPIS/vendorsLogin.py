import email
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import APIRouter, status, HTTPException , Response
from dataBase.dataBaseConnectivity import db
from debaggingFile.loggerFile import logger
from pydantic import  BaseModel
router = APIRouter()

vendore_collection = db["vendore_collection"]
jwttoken_toaddProduct = db["VendoreJwtTokenFile"]

SECRET_KEY = "VendoreDetails@{123_of_EcommersProdect@12334#@#!@#$4321}"
ALGORITHM = "HS256"

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/vendore_login")
async def vendore_login(vendoresData: LoginRequest, response: Response):

    email = vendoresData.email.strip().lower()
    password = vendoresData.password

    logger.info(
        f"Vendor login attempt started | email={email}"
    )

    if not email or not password:
        logger.warning(
            "Vendor login failed | Email or password missing"
        )
        raise HTTPException(
            status_code=400,
            detail="Email or Password is required"
        )

    try:
        venderEmailCheck = vendore_collection.find_one({"vendore_email": email})

    except Exception:
        logger.exception(
            f"Database error while finding vendor | email={email}"
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

    if not venderEmailCheck:
        logger.warning(
            f"Vendor email login failed | Email not found | email={email}"
        )
        raise HTTPException(
            status_code=401,
            detail="Incorrect email"
        )

    logger.debug(
        f"Vendor found in database | email={email}"
    )

    stored_password = venderEmailCheck["vendore_password"]

    if not bcrypt.checkpw(password.encode("utf-8"),stored_password.encode("utf-8")):
        logger.warning(
            f"Vendor password login failed | Incorrect password | email={email}"
        )
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )

    logger.info(
        f"Vendor password verification successful | email={email}"
    )

    role = venderEmailCheck.get("role", "vendor")

    sellerID = venderEmailCheck.get("seller_id")

    logger.info(
        f"for vendore email | {email}, getting sellerid from DB | {sellerID} "
    )

    now = datetime.now(timezone.utc)

    expire = now + timedelta(minutes=15)

    payload = {
        "vendore_email": email,
        "role": role,
        "type": "vendor",
        "exp": expire
    }

    try:
        token = jwt.encode(
            payload,
            SECRET_KEY,
            algorithm=ALGORITHM
        )

    except Exception:
        logger.exception(
            f"Failed to generate vendor JWT | email={email}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create authentication token"
        )

    logger.debug(
        f"Vendor JWT generated | email={email}"
    )

    try:
        jwttoken_toaddProduct.insert_one({
            "vendore_email": email,
            "token": token,
            "created_at": now,
            "expires_at": expire
        })

        jwttoken_toaddProduct.create_index(
            "expires_at",
            expireAfterSeconds=0
        )

        logger.info(
            f"Vendor product JWT stored successfully | email={email}"
        )

    except Exception:
        logger.exception(
            f"Failed to store vendor product JWT | email={email}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create authentication session"
        )

    response.set_cookie(
        key="vendor_access_token",
        value=token,
        max_age=15 * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    response.set_cookie(
        key="vendor_email",
        value=email,
        max_age=15 * 60,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    logger.info(
        f"Vendor login successful | email={email} | role={role}"
    )

    return {
        "message": "Login successful",
        "vendore_email": email,
        "role": role,
        "seller_id": sellerID
    }


