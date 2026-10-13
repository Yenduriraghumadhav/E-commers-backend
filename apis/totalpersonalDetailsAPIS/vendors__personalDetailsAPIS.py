from fileinput import filename
from http.client import HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
import gridfs
import phonenumbers
from fastapi import APIRouter, UploadFile, File, HTTPException, Response
import bcrypt
from fastapi import Cookie
import re
from starlette import status
from debaggingFile.loggerFile import logger
from schemas.totalpersonalDetailsSchemas.vendorsTableschema import VendorSchema
from schemas.vendoreJWTTokenSchema import VendoreJWTTokenRequest
from datetime import datetime, timedelta, timezone
from schemas.sellerAutoGenerateID import generate_seller_id
from dataBase.dataBaseConnectivity import db
import jwt
router = APIRouter()

vendore_collection = db["vendore_collection"]
jwttoken_toaddProduct = db["VendoreJwtTokenFile"]
fs = gridfs.GridFS(db)
vendore_bussins = db["Vendore_Bank_bussines_details"]

JWT_SECRET_KEY = "SRZvCv02LqEjQofXk4LBN6THYaWW9S_3PRCH2LE1dqJJfXF6fFvc0mVlRabgeWhx"
JWT_ALGORITHM = "HS256"

@router.post("/vendor_details")
async def create_vendor(vendor: VendorSchema,response: Response):

    password_pattern = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"
    if not re.match(password_pattern, vendor.vendore_password):
        logger.info(
            "Password must contain at least 8 characters, including alphabets, numbers, and a special symbol"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least 8 characters, including alphabets, numbers, and a special symbol"
        )

    existing_vendor = vendore_collection.find_one({
        "vendore_email": vendor.vendore_email
    })

    if existing_vendor:
        logger.warning("Vendor already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vendor already exists"
        )

    mobile_parsing = phonenumbers.parse(
        vendor.vendore_mobileNumber,
        vendor.vendore_country
    )

    if not phonenumbers.is_valid_number(mobile_parsing):
        logger.warning("Invalid mobile number")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid mobile number"
        )

    seller_id = generate_seller_id()

    vendor_data = vendor.model_dump()

    vendor_data.pop("vendore_Renter_Password", None)

    vendor_data["seller_id"] = seller_id

    vendor_data["role"] = "vendore"

    now = datetime.now(timezone.utc)

    expire = now + timedelta(minutes=15)

    hashed_password = bcrypt.hashpw(
        vendor_data["vendore_password"].encode("utf-8"),
        bcrypt.gensalt()
    )

    vendor_data["vendore_password"] = hashed_password.decode("utf-8")

    logger.info("Password hashing completed")

    vendore_collection.insert_one(vendor_data)

    logger.info("Vendor successfully added")

    jwt_payload = {
        "seller_id": seller_id,
        "vendore_email": vendor.vendore_email,
        "role": "vendore",
        "expires_at" : expire
    }

    token = jwt.encode(
        jwt_payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

    logger.info("JWT token created")

    jwttoken_toaddProduct.insert_one({
        "vendore_email": vendor.vendore_email,
        "token": token,
        "created_at": now,
        "expires_at": expire
    })

    jwttoken_toaddProduct.create_index(
        "expires_at",
        expireAfterSeconds=0
    )

    logger.info("JWT token stored in database")

    response.set_cookie(
        key="vendor_token",
        value=token,
        max_age=15 * 60,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    logger.info("JWT token sent as cookie")

    return {
        "message": "Vendor successfully added",
        "seller_id": seller_id,
        "vendore_email" : vendor.vendore_email,
        "role" : "vendore"
    }

class VendorUpdateSchema(BaseModel):
    vendore_name: Optional[str] = None
    vendore_email: Optional[EmailStr] = None
    vendore_mobileNumber: Optional[str] = None
    vendore_country: Optional[str] = None
    vendore_address: Optional[str] = None
    vendore_pincode: Optional[str] = None
    vendore_password: Optional[str] = None
    images: Optional[str] = None

@router.put("/vendor_details")
async def update_vendor(vendor_email: str,vendor: VendorUpdateSchema , vendor_access_token: str | None = Cookie(default=None)):

    if not vendor_access_token:
        logger.error("JWT token not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token is required"
        )

    token_exists = jwttoken_toaddProduct.find_one({"token": vendor_access_token})

    if not token_exists:
        logger.warning("Invalid JWT token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT token"
        )

    existing_vendor = vendore_collection.find_one({ "vendore_email": vendor_email })

    if not existing_vendor:
        logger.error(
            "vendore not found"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )

    update_data = vendor.model_dump(exclude_unset=True)

    if not update_data:
        logger.error(
            "no feilds provided to update"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    if "vendore_password" in update_data:

        password_pattern = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"

        if not re.match(password_pattern, update_data["vendore_password"]):
            logger.warning(
                "password must contain at least 8 characters including alphabets numbers and a special symbool"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least 8 characters, including alphabets, numbers, and a special symbol"
            )

        hashed_password = bcrypt.hashpw(
            update_data["vendore_password"].encode("utf-8"),
            bcrypt.gensalt()
        )

        update_data["vendore_password"] = hashed_password.decode("utf-8")

    result = vendore_collection.update_one(
        {"vendore_email": vendor_email},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        logger.warning(
            "No changes were made"
        )
        return {
            "message": "No changes were made"
        }

    logger.info(
        "Vedore successfully updated"
    )

    return {
        "message": "Vendor successfully updated",
        "updated_fields": list(update_data.keys())
    }

# @router.post("/vendor_imagess")
# async def upload_vendor_image( vendor_email: str,vendore_image: UploadFile = File(...)):
#     vendor = vendore_collection.find_one({
#         "vendore_email": vendor_email
#     })
#
#     if not vendor:
#         logger.warning(
#             "vendore not found in  DB "
#         )
#         raise HTTPException(
#             status_code=404,
#             detail="Vendor not found"
#         )
#
#     image_data = await vendore_image.read()
#
#     image_id = fs.put(
#         image_data,
#         filename=vendore_image.filename,
#         content_type=vendore_image.content_type
#     )
#
#     vendore_collection.update_one(
#         {"vendore_email": vendor_email},
#         {
#             "$set": {
#                 "images": image_id
#             }
#         }
#     )
#
#     logger.info(
#         "Image Uploaded Successfully"
#     )
#
#     return {
#         "message": "Image uploaded successfully",
#         "image_id": str(image_id)
#     }
#
#
# @router.put("/vendor_imagess")
# async def update_vendor_image(vendor_email: str, vendore_image: UploadFile = File(...),jwttoken: str | None = Cookie(default=None)):
#
#     if not jwttoken:
#         logger.warning(
#             "JWT token not provided"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="JWT token is required"
#         )
#
#     token_exists = jwttoken_toaddProduct.find_one({
#         "jwttoken": jwttoken
#     })
#
#     if not token_exists:
#         logger.warning(
#             "Invalid JWT token"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired JWT token"
#         )
#
#     vendor = vendore_collection.find_one({
#         "vendore_email": vendor_email
#     })
#
#     if not vendor:
#         logger.warning(
#             "Vendor not found in DB"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Vendor not found"
#         )
#
#     old_image_id = vendor.get("images")
#
#     if not old_image_id:
#         logger.warning(
#             "No existing image found"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="No existing image found. Use POST to upload an image."
#         )
#
#     image_data = await vendore_image.read()
#
#     if not image_data:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Image file is empty"
#         )
#
#     new_image_id = fs.put(
#         image_data,
#         filename=vendore_image.filename,
#         content_type=vendore_image.content_type
#     )
#
#     vendore_collection.update_one(
#         {"vendore_email": vendor_email},
#         {
#             "$set": {
#                 "images": new_image_id
#             }
#         }
#     )
#
#     try:
#         fs.delete(old_image_id)
#
#     except Exception as e:
#         logger.error(
#             f"New image uploaded but old image deletion failed: {str(e)}"
#         )
#
#     logger.info(
#         "Vendor image updated successfully"
#     )
#
#     return {
#         "message": "Vendor image updated successfully",
#         "image_id": str(new_image_id)
#     }

@router.delete("/vendor_details")
async def delete_vendor(vendor_email: str , vendor_access_token : str | None = Cookie(default=None)):

    vendor = vendore_collection.find_one({
        "vendore_email": vendor_email
    })

    if not vendor:
        logger.warning(
            "vendor not found in  DB "
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )

    result = vendore_collection.delete_one({
        "vendore_email": vendor_email
    })

    if result.deleted_count == 0:
        logger.warning(
            "Vendore Could Not deleted successfully"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor could not be deleted"
        )

    logger.info(
        "Vendor successfully deleted"
    )

    return {
        "message": "Vendor successfully deleted",
        "deleted_count": result.deleted_count
    }


@router.get("/vendorePersonalDetails")
async def get_vendor_personalDetails(email: str,vendor_access_token: str | None = Cookie(default=None)):

    if not vendor_access_token:
        logger.error("Vendor access token was not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not provided"
        )

    if not email or not email.strip():
        logger.error("Vendor email was not provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided"
        )

    try:
        filteringTokens = jwttoken_toaddProduct.find_one({
            "token": vendor_access_token
        })

        if not filteringTokens:
            logger.error("Vendor token not found in the database")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired or invalid"
            )

        vendorePerdonslDetasilsDta = {
            "_id": 0,
            "vendore_name": 1,
            "vendore_email": 1,
            "vendore_mobileNumber": 1,
            "vendore_country": 1,
            "vendore_address": 1,
            "vendore_pincode": 1,
            "seller_id": 1,
            "role": 1
        }

        filteringEmailss = vendore_collection.find_one(
            {"vendore_email": email.strip()},
            vendorePerdonslDetasilsDta
        )

        if not filteringEmailss:
            logger.error("Vendor email not found in the database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor email not found"
            )

        return {
            "status": "success",
            "message": "Vendor personal details fetched successfully",
            "PersonalDetails": filteringEmailss
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Error while fetching vendor personal details"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while fetching vendor personal details"
        )


class TotalBussinessDetails(BaseModel):
    Business_Email : str
    Business_Phone : str
    Business_Address : str
    GST_Number : str
    PAN_Number : str
    Bank_name : str
    Bank_ifsc : str
    Bank_pincode : str

class BusinessDetailsRequest(BaseModel):
    vendore_email: str
    details: TotalBussinessDetails


@router.post("/bussines_details")
async def busines_details(details: BusinessDetailsRequest,vendor_access_token: str | None = Cookie(default=None)):

    if not vendor_access_token:
        logger.warning(
            "Vendor business details failed | Access token missing"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vendor access token missing"
        )

    if not details:
        logger.warning(
            "Vendor business details failed | No business details provided"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No business details provided"
        )

    # if not vendore_email:
    #     logger.warning(
    #         "Vendor email not provided"
    #     )
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Vendor email not provided"
    #     )

    try:
        filteringToken = jwttoken_toaddProduct.find_one({
            "token": vendor_access_token
        })

        if not filteringToken:
            logger.warning(
                "Vendor token not found in DB"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token not found in DB"
            )

        logger.info(
            "Vendor token found in DB"
        )

        checkingEmail = vendore_collection.find_one({
            "vendore_email": details.vendore_email
        })

        if not checkingEmail:

            logger.warning(
                f"Vendor email not found in DB | "
                f"email={details.vendore_email}"
            )

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor email not found in DB"
            )

        logger.info(
            f"Vendor email found in DB | email={details.vendore_email}"
        )
        business_data = details.model_dump()
        business_data["vendore_email"] = details.vendore_email

        insert_result = vendore_bussins.insert_one(
            business_data
        )

        logger.info(
            f"Vendor business details inserted successfully | "
            f"email={details.vendore_email} | "
            f"id={insert_result.inserted_id}"
        )

        return {
            "message": "Business details saved successfully",
            "vendore_email": details.vendore_email,
            "business_id": str(insert_result.inserted_id)
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(
            f"Unexpected error while saving vendor business details | "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save business details"
        )


@router.get("/business_details")
async def getbussinesDetails(email: str, vendor_access_token:str | None = Cookie(default=None)):

    if not vendor_access_token:
        logger.error(
            "jwt token not provided "
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="jwt token not provided "
        )

    if not email:
        logger.error(
            "email  not provided "
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="email not provided "
        )

    try:

        fileterTOken = jwttoken_toaddProduct.find_one({"token" : vendor_access_token})

        if not fileterTOken:
            logger.error(
                "vendore token not found in DB "
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid"
            )

        filteringEMail = vendore_collection.find_one({"vendore_email" : email})

        if not filteringEMail:
            logger.warning(
                f"vendore email not found in DB file | {email}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not found  in DB "
            )

        gettingObjectData = {
            "_id": 0,
            "details.Business_Email": 1,
            "details.Business_Phone": 1,
            "details.Business_Address": 1,
            "details.GST_Number": 1,
            "details.PAN_Number": 1,
            "details.Bank_name": 1,
            "details.Bank_ifsc": 1,
            "details.Bank_pincode": 1
        }

        checkingEmailINBussinessDBFile = vendore_bussins.find_one({"vendore_email" : email} , gettingObjectData)

        logger.info(
            f" vendore bussiness details information | {checkingEmailINBussinessDBFile}"
        )

        if not checkingEmailINBussinessDBFile:
            logger.warning(
                f"vendore email not found in the Bussines DB File | {email}"
            )
            return {
                "message" : "No Bussines details provided For this email Please add Details ",
                "BusinessData" : []
            }


        return {
            "status" : "success",
            "BusinessData" : checkingEmailINBussinessDBFile
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Unexpected error while fetching vendor business details | "
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch business details"
        )




