from fastapi import APIRouter, Cookie, HTTPException, status
from  debaggingFile.loggerFile import logger
from dataBase.dataBaseConnectivity import db

router = APIRouter()
vendore_details = db["vendore_collection"]
productDetails = db["product_details"]
jwttoken_toaddProduct = db["VendoreJwtTokenFile"]
trakingOrders = db["TrakingOrders"]
vendorPerpose = db["TotalOrderDetailsForVendores"]


@router.get("/vendoreOrdersget")
async def vendoreOrdersGet(email: str,vendor_access_token: str | None = Cookie(default=None)):

    if not vendor_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vendor token not provided",
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided",
        )

    try:
        checking_jwt_token = jwttoken_toaddProduct.find_one({
            "token": vendor_access_token
        })

        if not checking_jwt_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired or invalid",
            )

        checking_vendor_email = vendore_details.find_one({
            "vendore_email": email
        })

        if not checking_vendor_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor email not found",
            )

        seller_id = checking_vendor_email.get("seller_id")

        if not seller_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Seller ID not found",
            )

        tracking_projection = {
            "_id": 0,
            "orderId": 1,
            "productId": 1,
            "Quality": 1,
            "userEmail": 1,
            "ordercreatedTime": 1,
        }

        tracking_orders = list(
            trakingOrders.find(
                {"seller_id": seller_id},
                tracking_projection
            )
        )

        if not tracking_orders:
            return {
                "success": True,
                "message": "No orders present",
                "ProductsData": []
            }

        product_projection = {
            "_id": 0,
            "product_name": 1,
            "brand_name": 1,
            "category": 1,
            "description": 1,
            "bullet_points": 1,
            "product_price": 1,
        }

        products_data = []

        for order in tracking_orders:
            product_id = order.get("productId")

            if not product_id:
                logger.warning(
                    "Product ID missing for order: %s",
                    order.get("orderId")
                )
                continue

            product = productDetails.find_one(
                {"product_id": product_id},
                product_projection
            )

            if not product:
                logger.warning(
                    "Product not found for productId: %s",
                    product_id
                )
                continue

            order_created_time = order.get("ordercreatedTime")

            if hasattr(order_created_time, "isoformat"):
                order_created_time = order_created_time.isoformat()

            products_data.append({
                "orderId": order.get("orderId"),
                "productId": product_id,
                "userEmail": order.get("userEmail"),
                "ordercreatedTime": order_created_time,
                "quality": order.get("Quality"),
                "productDetails": product,
            })

        return {
            "success": True,
            "message": "success" if products_data else "No product details found",
            "ProductsData": products_data
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Error while retrieving orders for vendor email: %s",
            email
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while retrieving vendor orders",
        )

