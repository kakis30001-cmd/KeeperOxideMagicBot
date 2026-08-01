import os
import secrets
import hmac
import hashlib
from config import ADMIN_IDS, CRYPTOBOT_TOKEN


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def generate_order_id(user_id: int, prefix: str = "ord") -> str:
    token = secrets.token_hex(6)
    return f"{prefix}_{user_id}_{token}"


def verify_crypto_signature(signature: str, body: bytes) -> bool:
    if not signature or not CRYPTOBOT_TOKEN:
        return False
    secret = hashlib.sha256(CRYPTOBOT_TOKEN.encode()).digest()
    calc = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, calc)


def apply_discount(price: int, discount_type: str, discount_value: int) -> int:
    if discount_type == "percent":
        return max(0, int(price * (1 - discount_value / 100)))
    elif discount_type == "fixed":
        return max(0, price - discount_value)
    return price


def escape_html(text: str | None) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def format_price(price: int) -> str:
    return f"{price:,} ₽".replace(",", " ")


def split_list(items: list, chunk_size: int = 2):
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
