from uuid import uuid4
from pydantic import BaseModel
from fastapi import APIRouter, status, HTTPException, Cookie , BackgroundTasks
from datetime import datetime , timezone
from debaggingFile.loggerFile import logger
from Email_utility.order_email_utils import send_order_placement_emails
from dataBase.dataBaseConnectivity import db
from dotenv import load_dotenv
load_dotenv()

router = APIRouter()
user_JWTToken = db["Userslogin_history"]
Athentications = db["AthenticationPerpose"]
users_collection = db["usersDetails"]
odersList = db["UsersOrdersDeatils"]
productDetails = db["product_details"]
vendore_collection = db["vendore_collection"]
trakingOrders = db["TrakingOrders"]
vendorPerpose = db["TotalOrderDetailsForVendores"]


class ProductOrder(BaseModel):
    productId: str
    Quality: str
    productCost: str

class oderListCreate(BaseModel):
    userEmail: str
    phoneNumber: str
    addressLine: str
    Pincode: str
    products: list[ProductOrder]
    Ordered: bool | None = None
    Shipped: bool | None = None
    Outfordelivery: bool | None = None
    Arriving: bool | None = None

def send_order_emails_in_background(user_email: str, vendor_products: dict,order_id: str, phone_number: str,address_line: str,pincode: str,):
    try:
        send_order_placement_emails(
            user_email=user_email,
            vendor_products=vendor_products,
            order_id=order_id,
            phone_number=phone_number,
            address_line=address_line,
            pincode=pincode,
        )
    except Exception:
        logger.exception(
            "Unexpected error while sending order emails. order_id=%s",
            order_id,
        )


@router.post("/usersorders")
async def usersordersget(data: oderListCreate, background_tasks: BackgroundTasks, userEmail: str, jwt_Token: str | None = Cookie(default=None),):

    if not jwt_Token:
        logger.error("JWT token not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized access",
        )

    temporary_user = Athentications.find_one({
        "token": jwt_Token
    })

    if temporary_user:
        logger.warning(
            "Temporary user %s tried to place an order",
            userEmail,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please login as user to buy the product",
        )

    permanent_user = user_JWTToken.find_one({
        "token": jwt_Token
    })

    if not permanent_user:
        logger.error(
            "Invalid JWT token for %s",
            userEmail,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized access",
        )

    order_id = str(uuid4())

    logger.info(
        "New checkout started. order_id=%s",
        order_id,
    )

    ordered_products = []
    vendor_products = {}

    for item in data.products:
        logger.info(
            "Product ID from frontend: %s",
            item.productId,
        )

        product = productDetails.find_one({
            "product_id": item.productId
        })

        if not product:
            logger.warning(
                "Product %s not found",
                item.productId,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {item.productId} not found in the DB",
            )

        seller_id = product.get("seller_id")

        if not seller_id:
            logger.error(
                "seller_id not found for product %s",
                item.productId,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Seller ID not found for product {item.productId}",
            )

        vendor = vendore_collection.find_one({
            "seller_id": seller_id
        })

        if not vendor:
            logger.error(
                "Vendor not found for seller_id=%s",
                seller_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor details not found",
            )

        vendor_email = vendor.get("vendore_email")

        if not vendor_email:
            logger.error(
                "Vendor email not found for seller_id=%s",
                seller_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor email not found",
            )

        try:
            odersList.insert_one({
                "order_id": order_id,
                "userEmail": userEmail,
                "phoneNumber": data.phoneNumber,
                "addressLine": data.addressLine,
                "Pincode": data.Pincode,
                "productId": item.productId,
                "Quality": item.Quality,
                "productCost": item.productCost,
                "seller_id": seller_id,
                "vendore_email": vendor_email,
                "Trackorder": "NOT DELIVERED",
            })

            logger.info(
                "Order product inserted. order_id=%s, productId=%s",
                order_id,
                item.productId,
            )

        except Exception:
            logger.exception(
                "Failed to insert order. order_id=%s, productId=%s",
                order_id,
                item.productId,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something went wrong while placing the order",
            )

        try:
            tracking_order = {
                "orderId": order_id,
                "userEmail": userEmail,
                "seller_id": seller_id,
                "orderEmail": data.userEmail,
                "phoneNumber": data.phoneNumber,
                "addressLine": data.addressLine,
                "Pincode": data.Pincode,
                "productId": item.productId,
                "Quality": item.Quality,
                "Ordered": True,
                "Shipped": False,
                "Outfordelivery": False,
                "Arriving": False,
                "ordercreatedTime": datetime.now(timezone.utc),
            }

            trakingOrders.insert_one(tracking_order)

            logger.info(
                "Tracking created successfully. order_id=%s, productId=%s",
                order_id,
                item.productId,
            )

        except Exception:
            logger.exception(
                "Failed to create order tracking. order_id=%s",
                order_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Order was created but order tracking "
                    "could not be created"
                ),
            )

        # --- MOVED INSIDE THE LOOP BELOW ---
        try:
            objectOrderDta = {
                "order_id": order_id,
                "seller_id": seller_id,
                "productId": item.productId,
                "Quality": item.Quality,
                "orderDate": datetime.now(timezone.utc)
            }

            insertingOders = vendorPerpose.insert_one(objectOrderDta)

            logger.info(
                f"vendor order details stored successfully in Db | {insertingOders.inserted_id}"
            )
        except Exception:
            logger.exception("Failed to insert into vendorPerpose")

        ordered_products.append({
            "productId": item.productId,
            "Quality": item.Quality,
            "productCost": item.productCost,
        })

        if vendor_email not in vendor_products:
            vendor_products[vendor_email] = {
                "seller_id": seller_id,
                "products": [],
            }

        vendor_products[vendor_email]["products"].append({
            "productId": item.productId,
            "Quality": item.Quality,
            "productCost": item.productCost,
        })

        # Background task and return remain outside the loop
    background_tasks.add_task(
        send_order_emails_in_background,
        data.userEmail,
        vendor_products,
        order_id,
        data.phoneNumber,
        data.addressLine,
        data.Pincode,
    )

    logger.info(
        "Order emails scheduled. order_id=%s, user=%s, vendor_count=%s",
        order_id,
        userEmail,
        len(vendor_products),
    )

    logger.info(
        "Order completed successfully. order_id=%s, user=%s",
        order_id,
        userEmail,
    )

    return {
        "status": "success",
        "message": "Order placed successfully",
        "order_id": order_id,
    }


@router.get("/viewOrders")
async def viewOrders(userEmail: str,jwt_Token: str | None = Cookie(default=None)):

    if not userEmail:
        logger.error("Email not provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided"
        )

    if not jwt_Token:
        logger.error("JWT token not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized access"
        )

    checking = user_JWTToken.find_one({
        "token": jwt_Token
    })

    if not checking:
        logger.error(
            f"Invalid JWT token for {userEmail}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized access"
        )

    orders = list(
        odersList.find({
            "userEmail": userEmail
        })
    )

    if not orders:
        logger.warning(
            f"No orders found for {userEmail}"
        )

        return {
            "status": "success",
            "message": "Order now",
            "productDetails": []
        }

    product_details = []

    for order in orders:

        product_id = order.get("productId")

        if not product_id:
            logger.warning(
                f"ProductId not found for user {userEmail}"
            )
            continue

        quality = order.get("Quality")

        logger.info(
            f"product quality : {quality}"
        )

        product = productDetails.find_one({
            "product_id": product_id
        })

        if not product:
            logger.warning(
                f"Product {product_id} not found in product_details"
            )

            product_details.append({
                "order_id": order.get("order_id"),
                "userEmail": order.get("userEmail"),
                "phoneNumber": order.get("phoneNumber"),
                "addressLine": order.get("addressLine"),
                "Pincode": order.get("Pincode"),
                "productId": product_id,
                "Quality": order.get("Quality"),
                "productCost": order.get("productCost"),
                "product_name": None,
                "brand_name": None,
                "category": None,
                "description": None,
                "bullet_points": None,
                "product_price": None,
                "product_mrp": None,
                "productFound": False
            })

            continue

        product_details.append({
            "order_id": order.get("order_id"),
            "userEmail": order.get("userEmail"),
            "phoneNumber": order.get("phoneNumber"),
            "addressLine": order.get("addressLine"),
            "Pincode": order.get("Pincode"),
            "productId": product_id,
            "Quality": order.get("Quality"),
            "productCost": order.get("productCost"),
            "product_name": product.get("product_name"),
            "brand_name": product.get("brand_name"),
            "category": product.get("category"),
            "description": product.get("description"),
            "bullet_points": product.get("bullet_points"),
            "product_price": product.get("product_price"),
            "product_mrp": product.get("product_mrp"),
            "productFound": True
        })

    logger.info(
        f"User order data sent successfully for {userEmail}"
    )

    return {
        "status": "success",
        "message": "Ordered products",
        "productDetails": product_details
    }



