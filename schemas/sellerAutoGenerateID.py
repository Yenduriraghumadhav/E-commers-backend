import random
import string


def generate_seller_id():
    characters = string.ascii_uppercase + string.digits

    random_part = ''.join(
        random.choices(characters, k=8)
    )

    return f"SELLER-{random_part}"
