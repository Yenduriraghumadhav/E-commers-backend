import datetime
from datetime import datetime
from fastapi import APIRouter , Cookie , HTTPException,status
from pydantic import BaseModel

from dataBase.dataBaseConnectivity import db
from debaggingFile.loggerFile import logger

router = APIRouter()
jwt_TokenFiltterization = db["Userslogin_history"]
Add_ToCart = db["Add_ToCartUsersProducts"]
productDetails = db["product_details"]

class UserCartItemRequest(BaseModel):
    product_id : str
    seller_id : str

@router.post("/users_ADDTOCART")
async def UsersADDTOCART(userEmail: str, data: UserCartItemRequest,jwt_Token: str | None = Cookie(default=None)):

    if not jwt_Token:
        logger.error("jwt_token not provided")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="jwt_token not provided"
        )

    if not userEmail:
        logger.error("userEmail not provided")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="userEmail not provided"
        )

    if not data:
        logger.error("data not provided")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data not provided"
        )

    if not data.product_id:
        logger.error("product_id not provided")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product_id not provided"
        )

    try:
        filtering = jwt_TokenFiltterization.find_one({
            "token": jwt_Token
        })

        if not filtering:
            logger.error("token not Found in DB")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthenticated User"
            )

        product_id = data.product_id
        seller_id = data.seller_id

        logger.info(
            f"Add to cart request | "
            f"userEmail={userEmail} | "
            f"product_id={product_id}"
        )

        existingProduct = Add_ToCart.find_one({
            "userEmail": userEmail,
            "product_id": product_id
        })

        if existingProduct:
            logger.info(
                f"Product already exists in cart | "
                f"userEmail={userEmail} | "
                f"product_id={product_id}"
            )

            return {
                "status": "success",
                "message": "Product already exists in cart",
                "product_id": product_id
            }

        now = datetime.now()

        Add_ToCart.insert_one({
            "userEmail": userEmail,
            "product_id": product_id,
            "orderDate": now,
            "orderTime": now.strftime("%H:%M:%S"),
            "seller_id": seller_id,
            "status": "active"
        })

        logger.info(
            f"Product added to cart successfully | "
            f"userEmail={userEmail} | "
            f"product_id={product_id}"
        )

        return {
            "status": "success",
            "message": "Product added to cart successfully",
            "product_id": product_id
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "ADD TO CART details failed to send to DB"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )


@router.get("/usersGETData")
async def getUsersData(userEmail: str,jwt_Token: str | None = Cookie(default=None)):

    try:
        if not jwt_Token:
            logger.error("jwt_token not provided")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        filteringData = jwt_TokenFiltterization.find_one({
            "token": jwt_Token
        })

        if not filteringData:
            logger.error("JWT token not found in database")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        userData = list(
            Add_ToCart.find(
                {
                    "userEmail": userEmail
                },
                {
                    "_id": 0,
                    "product_id": 1
                }
            )
        )

        logger.info(
            f"Cart data found | email={userEmail} | count={len(userData)}"
        )

        if not userData:
            logger.info(
                f"Cart is empty | email={userEmail}"
            )

            return {
                "status": "success",
                "message": "Add a product to your cart",
                "products": []
            }

        product_ids = [
            item["product_id"]
            for item in userData
            if item.get("product_id")
        ]

        logger.info(
            f"Product IDs from cart | "
            f"email={userEmail} | "
            f"product_ids={product_ids}"
        )

        gettingProducts = list(
            productDetails.find(
                {
                    "product_id": {
                        "$in": product_ids
                    }
                },
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
                    "seller_id": 1
                }
            )
        )

        logger.info(
            f"Products found in productDetails | "
            f"email={userEmail} | "
            f"count={len(gettingProducts)}"
        )

        return {
            "status": "success",
            "products": gettingProducts
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("getUsersData failed")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )


@router.delete("/usersDataDelete")
async def deleteUsersData( userEmail: str, productId : str , jwt_Token : str | None = Cookie(default=None)):

    if not jwt_Token:
        logger.error(
            "jwt_token not provided"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if not userEmail:
        logger.error(
            "userEmail not provided"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if not productId:
        logger.error(
            "productId not provided"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    try:
        chekingProductJWTTOKEN = jwt_TokenFiltterization.find_one({"token" : jwt_Token})

        if not chekingProductJWTTOKEN:
            logger.error(
                "Jwt_token not found in database"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication Failed"
            )
        if chekingProductJWTTOKEN:

            deletingProduct = Add_ToCart.delete_one({"userEmail" : userEmail , "product_id" : productId})

            if deletingProduct.deleted_count == 0:
                logger.warning(
                    f"ProductID {productId} did not exist in cart"
                )

                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product does not exist in cart"
                )

            return {
                "status": "success",
                "message": "Product removed from cart successfully"
            }
    except:
        logger.error(
            "ADD TO CART DELETE API details Feild"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR_BAD_REQUEST,
            detail="Internal Server Error"
        )





