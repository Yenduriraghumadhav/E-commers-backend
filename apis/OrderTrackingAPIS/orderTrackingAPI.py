from fastapi import APIRouter, Cookie, status, HTTPException , BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, timezone
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
deletedTrackingOrders = db["CancelOdersTrakingData"]
vendorPerpose = db["TotalOrderDetailsForVendores"]


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
async def UserDeletingOrder( data: gettingDeleteRequiredThings, background_tasks: BackgroundTasks,email: str,jwt_Token: str = Cookie(default=None),):

    if not jwt_Token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not provided",
        )

    if not email or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided",
        )

    checkingUserJwtToken = user_JWTToken.find_one({
        "token": jwt_Token
    })

    if not checkingUserJwtToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        user_order = odersList.find_one({
            "order_id": data.orderId,
            "productId": data.productId,
            "userEmail": email.strip(),
        })

        if not user_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found for this user",
            )

        user_email = user_order.get("userEmail")

        tracking_record = trakingOrders.find_one({
            "orderId": data.orderId,
            "productId": data.productId,
        })

        if not tracking_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking record not found",
            )

        filteringordersdata = vendorPerpose.find_one({
            "orderEmail" : email,
            "order_id": data.orderId,
            "productId": data.productId,
        })

        if filteringordersdata:
            vendorPerpose.update_one(
                {"_id": filteringordersdata["_id"]},
                {"$set": {"CancelOrder": "cancelled"}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor order record not found",
            )

        logger.info(
            f"order cancel is enter in the vendoreperspose Db file | {filteringordersdata}"
        )

        product = productDetails.find_one({
            "product_id": data.productId
        })

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        vendor_email = product.get("vendor_email")
        product_name = product.get("product_name", "Unknown Product")
        cancellation_record = tracking_record.copy()
        cancellation_record["original_tracking_id"] = tracking_record["_id"]
        cancellation_record.pop("_id", None)

        cancellation_record["cancellation_details"] = {
            "cancelled_by": user_email,
            "cancelled_at": datetime.now(timezone.utc),
            "order_id": data.orderId,
            "product_id": data.productId,
        }

        cancelorder = deletedTrackingOrders.insert_one(
            cancellation_record
        )

        logger.info(
            "Cancellation record saved. ID: %s",
            cancelorder.inserted_id,
        )

        tracking_delete = trakingOrders.delete_one({
            "_id": tracking_record["_id"]
        })

        if tracking_delete.deleted_count != 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cancellation saved, but tracking deletion failed",
            )

        order_delete = odersList.delete_one({
            "_id": user_order["_id"]
        })

        if order_delete.deleted_count != 1:
            logger.error(
                "Tracking deleted, but order deletion failed. "
                "Order=%s Product=%s",
                data.orderId,
                data.productId,
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tracking deleted, but order deletion failed",
            )

        if user_email and vendor_email:
            background_tasks.add_task(
                send_cancellation_emails,
                user_email,
                vendor_email,
                str(data.orderId),
                str(data.productId),
                str(product_name),
            )
            email_status = "scheduled"
        else:
            email_status = "not scheduled"

        return {
            "status": "success",
            "message": "Order cancelled successfully",
            "order": data.orderId,
            "product": data.productId,
            "cancellation_record_id": str(cancelorder.inserted_id),
            "email_notifications": email_status,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Error cancelling order %s, product %s",
            data.orderId,
            data.productId,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while cancelling the order",
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


