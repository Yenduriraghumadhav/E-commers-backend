
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


def send_cancellation_email(
    recipient: str,
    subject: str,
    body: str,
) -> None:
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials are not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_EMAIL
    message["To"] = recipient
    message.set_content(body)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(message)


def send_cancellation_emails(
    user_email: str,
    vendor_email: str,
    order_id: str,
    product_id: str,
    product_name: str,
) -> None:

    notifications = [
        (
            user_email,
            "Your order has been cancelled",
            (
                "Hello,\n\n"
                "Your order item has been cancelled successfully.\n\n"
                f"Order ID: {order_id}\n"
                f"Product: {product_name}\n"
                f"Product ID: {product_id}\n\n"
                "If you have questions, please contact our support team."
            ),
        ),
        (
            vendor_email,
            "Order cancellation notification",
            (
                "Hello Vendor,\n\n"
                "An order item associated with your product has been cancelled.\n\n"
                f"Order ID: {order_id}\n"
                f"Product: {product_name}\n"
                f"Product ID: {product_id}\n\n"
                "Please update your order processing records accordingly."
            ),
        ),
    ]

    for recipient, subject, body in notifications:
        try:
            send_cancellation_email(recipient, subject, body)
            logger.info(
                "Cancellation email sent to %s for order %s",
                recipient,
                order_id,
            )
        except Exception:
            logger.exception(
                "Cancellation email failed for order %s, recipient %s",
                order_id,
                recipient,
            )
