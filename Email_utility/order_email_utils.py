import os
import smtplib
import logging
from email.message import EmailMessage
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")


def send_order_email(
    recipient: str,
    subject: str,
    body: str,
) -> None:
    if not SMTP_EMAIL or not SMTP_PASSWORD:raise RuntimeError("SMTP credentials are not configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_EMAIL
    message["To"] = recipient
    message.set_content(body)

    with smtplib.SMTP_SSL(
        SMTP_HOST,
        SMTP_PORT,
        timeout=15,
    ) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(message)


def send_order_placement_emails(
    user_email: str,
    vendor_products: dict,
    order_id: str,
    phone_number: str,
    address_line: str,
    pincode: str,
) -> None:

    user_body = (
        "Hello,\n\n"
        "Your order has been placed successfully!\n\n"
        f"Order ID: {order_id}\n\n"
        "Delivery Details:\n"
        f"Phone Number: {phone_number}\n"
        f"Address: {address_line}\n"
        f"Pincode: {pincode}\n\n"
        "Thank you for shopping with us!"
    )

    try:
        send_order_email(
            recipient=user_email,
            subject="Order Placed Successfully",
            body=user_body,
        )

        logger.info(
            "Order confirmation email sent to %s for order %s",
            user_email,
            order_id,
        )

    except Exception:
        logger.exception(
            "Order confirmation email failed for order %s, recipient %s",
            order_id,
            user_email,
        )

    for vendor_email, vendor_data in vendor_products.items():
        products = vendor_data.get("products", [])

        product_details = "\n".join(
            (
                f"Product ID: {product.get('product_id')}\n"
                f"Product Name: {product.get('product_name', 'N/A')}\n"
                f"Quantity: {product.get('quantity')}\n"
                f"Price: {product.get('price')}\n"
            )
            for product in products
        )

        vendor_body = (
            "Hello Vendor,\n\n"
            "You have received a new order!\n\n"
            f"Order ID: {order_id}\n"
            f"Seller ID: {vendor_data.get('seller_id', 'N/A')}\n\n"
            "Ordered Products:\n"
            f"{product_details}\n"
            "Customer Details:\n"
            f"Email: {user_email}\n"
            f"Phone Number: {phone_number}\n"
            f"Address: {address_line}\n"
            f"Pincode: {pincode}\n\n"
            "Please process this order."
        )

        try:
            send_order_email(
                recipient=vendor_email,
                subject="New Order Received",
                body=vendor_body,
            )

            logger.info(
                "Vendor order email sent to %s for order %s",
                vendor_email,
                order_id,
            )

        except Exception:
            logger.exception(
                "Vendor order email failed for order %s, recipient %s",
                order_id,
                vendor_email,
            )