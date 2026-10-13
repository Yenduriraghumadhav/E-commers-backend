from fastapi import APIRouter, Cookie, status, HTTPException , BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from debaggingFile.loggerFile import logger
from dataBase.dataBaseConnectivity import db
from Email_utility.email_utils import (send_cancellation_email, send_cancellation_emails)

router = APIRouter()
trakingOrders = db["TrakingOrders"]
user_JWTToken = db["Userslogin_history"]
productDetails = db["product_details"]
vendore_collection = db["vendore_collection"]
jwttoken_toaddProduct = db["VendoreJwtTokenFile"]
users_collection = db["usersDetails"]
odersList = db["UsersOrdersDeatils"]


@router.get("/trakingUserOrder")
async def UsersTrakingOrder(email: str,role: str, jwt_Token: str = Cookie(default=None)):

    logger.info(
        f"========== /trakingUserOrder CALLED =========="
    )

    logger.info(
        f"email={email}, role={role}"
    )

    if not jwt_Token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT Token not provided"
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User Email not provided"
        )

    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User role not provided"
        )

    if role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user role"
        )

    checkingtheUser = user_JWTToken.find_one({
        "token": jwt_Token
    })

    if not checkingtheUser:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT Token"
        )

    tracking_records = list(
        trakingOrders.find({
            "userEmail": email.strip().lower()
        })
    )

    if not tracking_records:
        return {
            "message": "No orders found",
            "productDetails": []
        }

    productDetails = []

    for tracking in tracking_records:

        productDetails.append({
            "orderId": str(tracking.get("orderId", "")),
            "productId": tracking.get("productId"),
            "ordered": tracking.get("Ordered", False),
            "Shipped": tracking.get("Shipped", False),
            "Outfordelivery": tracking.get(
                "Outfordelivery", False
            ),
            "Arriving": tracking.get("Arriving", False),
            "ordercreatedTime": tracking.get("ordercreatedTime"),
        })

    return {
        "message": "Orders found successfully",
        "productDetails": productDetails
    }

class gettingDeleteRequiredThings(BaseModel):
    productId : str
    orderId : str

@router.delete("/DeletingtrakingOrders")
async def UserDeletingOrder(data: gettingDeleteRequiredThings,background_tasks: BackgroundTasks,email: str, jwt_Token: str = Cookie(default=None),):

    if not jwt_Token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token not provided",
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not provided",
        )

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="data not provided",
        )

    checkingUserJwtToken = user_JWTToken.find_one({"token" : jwt_Token})

    if not checkingUserJwtToken:
        logger.error(
            f"Jwt token was not found in DB"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jwt token not found",
        )

    try:
        user_order = odersList.find_one({
            "order_id": data.orderId,
            "productId": data.productId
        })

        if not user_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found for this user",
            )

        user_email = user_order.get("userEmail")


        product = productDetails.find_one({
            "product_id": data.productId,
        })

        vendor_email = None
        product_name = str(data.productId)

        if product:
            vendor_email = product.get("vendor_email")
            product_name = product.get(
                "product_name",
                str(data.productId),
            )

            if vendor_email:
                logger.info("Vendor email found")
            else:
                logger.warning(
                    "Vendor email not found for product %s",
                    data.productId,
                )
        else:
            logger.warning(
                "Product details not found for product %s",
                data.productId,
            )

        tracking_record = trakingOrders.find_one({
            "orderId": data.orderId,
            "productId": data.productId,
        })

        if not tracking_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking record not found",
            )

        tracking_delete = trakingOrders.delete_one({
            "_id": tracking_record["_id"],
        })

        if tracking_delete.deleted_count != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tracking record was not deleted",
            )

        order_delete = odersList.delete_one({
            "_id": user_order["_id"],
        })

        if order_delete.deleted_count != 1:
            logger.error(
                "Tracking record deleted, but order deletion failed. "
                "Order=%s Product=%s",
                data.orderId,
                data.productId,
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Order deletion failed; please contact support",
            )

        if user_email:
            background_tasks.add_task(
                send_cancellation_emails,
                user_email,
                vendor_email or "",
                str(data.orderId),
                str(data.productId),
                str(product_name),
            )

            logger.info(
                "Cancellation email task scheduled for order %s",
                data.orderId,
            )
        else:
            logger.warning(
                "Order cancelled, but customer email is missing"
            )

        return {
            "message": "deleted successfully",
            "order": data.orderId,
            "product": data.productId,
            "email_notifications": (
                "scheduled" if user_email else "not scheduled"
            ),
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Error deleting order %s, product %s",
            data.orderId,
            data.productId,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong",
        )

@router.get("/trakingVendoreOrder")
async def VendoregetTrakingOrder(seller_id: str,role: str,vendor_access_token: str = Cookie(default=None)):

    if not vendor_access_token:
        logger.error(
            "JWT Token was not provided. Please provide a valid JWT Token."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT Token not provided",
        )

    if not seller_id:
        logger.error(
            "seller_id was not provided. Please provide a valid seller_id."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="seller_id not provided",
        )

    if not role:
        logger.error(
            " role was not provided. Please provide a valid User Role"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="role not provided",
        )

    if role == "vendor":
        checkingtheUser = jwttoken_toaddProduct.find_one({"token": vendor_access_token})

        if not checkingtheUser:
            logger.error(
                "vendore role was not found in the DB"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Jwt Token",
            )

        TrakingData = await trakingOrders.find({"seller_id": seller_id})

        if not TrakingData:
            logger.info(
                f"No order tracking data found for {seller_id}"
            )
            return {
                "message": "No orders found",
                "productDetails": None
            }

        productData = {
            "ordered": TrakingData.get("Ordered"),
            "Shipped": TrakingData.get("Shipped"),
            "Outfordelivery": TrakingData.get("Outfordelivery"),
            "Arriving": TrakingData.get("Arriving")
        }

        logger.info(
            f"Tracking data found successfully for {seller_id}"
        )
        return {
            "message": "Order found successfully",
            "productDetails": productData
        }
    else:
        logger.warning(
            f"Invalid role received: {role}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user role"
        )


