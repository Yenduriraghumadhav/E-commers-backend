from fastapi import APIRouter , Cookie , status ,HTTPException
from dataBase.dataBaseConnectivity import db
from debaggingFile.loggerFile import logger
router = APIRouter()
productDetails = db["product_details"]
user_JWTToken = db["Userslogin_history"]
Athentications = db["AthenticationPerpose"]
users_collection = db["usersDetails"]
vendore_collection = db["vendore_collection"]
jwttoken_toaddProduct = db["VendoreJwtTokenFile"]


@router.get("/TProductsDL")
async def productsDL( userEmail: str ,jwt_Token: str | None = Cookie(default=None)):

    try:

        if not jwt_Token:
            logger.error("JWT TOKEN Not Provided")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT TOKEN Not Provided"
            )

        checkingTemporary = Athentications.find_one({"email": userEmail})

        if checkingTemporary:
            logger.info("Temporary User")
        else:
            permanentUser = users_collection.find_one({
                "userEmail": userEmail
            })

            if not permanentUser:
                logger.error("User Email Not Found in DB")

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized User"
                )

            logger.info("Permanent User")

        products = list(
            productDetails.find(
                {},
                {
                    "_id": 0,
                    "product_id": 1,
                    "product_name": 1,
                    "brand_name": 1,
                    "category": 1,
                    "description": 1,
                    "bullet_points": 1,
                    "product_price": 1,
                    "product_mrp": 1,
                    "product_quantity": 1,
                    "seller_id": 1
                }
            )
        )

        return {
            "status": "success",
            "products": products
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("Something went wrong")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong"
        )


@router.get("/VendoreTotalProducts")
async def vendoreProducts(email: str, vendor_access_token: str | None = Cookie(default=None)):

    if not vendor_access_token:
        logger.warning("Vendor token not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vendor Token Not Provided"
        )

    if not email or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email Not Provided"
        )

    try:
        checkingJWTToken = jwttoken_toaddProduct.find_one(
            {"token": vendor_access_token}
        )

        if not checkingJWTToken:
            logger.warning("Vendor JWT token not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT Token Not Found"
            )

        checkingTheEmail = vendore_collection.find_one(
            {"vendore_email": email}
        )

        if not checkingTheEmail:
            logger.warning(f"Vendor email not found: {email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor email not found in DB"
            )

        sellerID = checkingTheEmail.get("seller_id")

        if not sellerID:
            logger.warning(f"seller_id not found for {email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Seller ID not found for this vendor"
            )

        logger.info(f"Getting products for seller_id: {sellerID}")

        gettingProducts = list(
            productDetails.find({"seller_id": sellerID})
        )

        for product in gettingProducts:
            if "_id" in product:
                product["_id"] = str(product["_id"])

        if not gettingProducts:
            return {
                "status": "success",
                "message": "No products found. Please add your products.",
                "seller_id": sellerID,
                "total_products": 0,
                "products": []
            }

        return {
            "status": "success",
            "seller_id": sellerID,
            "total_products": len(gettingProducts),
            "products": gettingProducts
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("Error while retrieving vendor products")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while retrieving products"
        )
