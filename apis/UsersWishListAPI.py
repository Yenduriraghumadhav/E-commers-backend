from debaggingFile.loggerFile import logger
from fastapi import  APIRouter , Cookie , HTTPException , status
from dataBase .dataBaseConnectivity import db
router = APIRouter()
Filtterization = db["Userslogin_history"]
wishlistDB = db["UsersWishList_History"]
productDetails = db["product_details"]


@router.post("/whishList")
async def WhishListAPi( productId :str , userEmail : str , jwt_Token: str | None = Cookie(default=None)):

    if not jwt_Token:
        logger.info(
            "jwt_token is Not Provided"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    if not userEmail:
        logger.warning(
            "userEmail is Not Provided"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The email field cannot be empty",
        )


    if not productId:
        logger.warning(
            "productId is Not Provided"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="productId is required",
        )

    filteringData = Filtterization.find_one({"token" : jwt_Token})

    if not filteringData:
        logger.warning(
            "jwt token not found on DB"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    alreadyExisting = wishlistDB.find_one({"product_id" : productId ,"userEmail": userEmail,})

    if alreadyExisting:
        logger.info(
            "the productID already add to wishlist "
        )
        return {
            "status": "success",
            "message" : "Product already exists in wishlist DB"
        }

    if not alreadyExisting:
        try:
            sendingData = wishlistDB.insert_one({
                "userEmail": userEmail,
                "product_id": productId
            })

            logger.info(
                f"wishlist data inserted into DB | {sendingData}"
            )
            return {
                "status": "success",
                "message": "wishlist data inserted successfully",
            }
        except:
            logger.warning(
                "wishlistDB insertion failed on DB"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error",
        )


@router.delete("/wishlistremove")
async def WishListDelete( userEmail : str , productId :str , jwt_Token : str | None = Cookie(default=None)):

    if not jwt_Token:
        logger.warning(
            "jwt_token is Not Provided"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The token was not provided",
        )

    if not userEmail:
        logger.warning(
            "userEmail is Not Provided"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email field cannot be empty",
        )

    if not productId:
        logger.warning(
            "productId is not provided"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="productId is not provided",
        )

    ChecckingJWTTOKEN = Filtterization.find_one({"token": jwt_Token})

    if not ChecckingJWTTOKEN:
        logger.warning(
            "jwt token not found on DB"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    try:
        DeletingDate = wishlistDB.delete_one({"userEmail" : userEmail , "product_id" : productId})

        logger.info(
            f"Matching wishlist data = {DeletingDate}"
        )

        if DeletingDate.deleted_count == 0:
            logger.warning(
                f"No wishlist document found | "
                f"userEmail={userEmail}, productId={productId}"
            )

        else:
            logger.info(
                f"Wishlist data deleted successfully | "
                f"userEmail={userEmail}, productId={productId}"
            )
    except:
        logger.warning(
            "wishlistDB deletion failed on DB"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error",
        )


@router.get("/viewWishList")
async def WishListView(userEmail: str, jwt_Token: str | None = Cookie(default=None)):

    if not jwt_Token:
        logger.warning("jwt_token is not provided")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The token was not provided"
        )

    try:
        checkingToken = Filtterization.find_one({
            "token": jwt_Token
        })

        if not checkingToken:
            logger.warning("jwt_token not found in DB")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        wishlist_data = list(
            wishlistDB.find(
                {
                    "userEmail": userEmail
                },
                {
                    "_id": 0,
                    "product_id": 1
                }
            )
        )

        if not wishlist_data:
            logger.info(
                f"Wishlist not found | email={userEmail}"
            )

            return {
                "status": "success",
                "message": "Add product to the Wishlist",
                "wishList": []
            }

        product_ids = [
            item["product_id"]
            for item in wishlist_data
            if item.get("product_id")
        ]

        if not product_ids:
            return {
                "status": "success",
                "message": "Add product to the Wishlist",
                "wishList": []
            }

        logger.info(
            f"Wishlist product IDs | email={userEmail} | "
            f"product_ids={product_ids}"
        )

        products = list(
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
                    "product_quantity": 1
                }
            )
        )

        logger.info(
            f"Wishlist found successfully | "
            f"email={userEmail} | "
            f"total_products={len(products)}"
        )

        return {
            "status": "success",
            "message": "Wishlist found successfully",
            "totalProducts": len(products),
            "wishList": products
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(
            f"Error while viewing wishlist | "
            f"email={userEmail} | error={e}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong"
        )
