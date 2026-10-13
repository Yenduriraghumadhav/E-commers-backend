import logging
import os
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR,"application.log")
logger = logging.getLogger("EcommerceApp")
logger.setLevel(logging.DEBUG)

if not logger.handlers:

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )


    formatter = logging.Formatter(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(filename)s:%(lineno)d | "
        "%(message)s"
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    logger.propagate = False
