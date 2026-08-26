import hashlib
import hmac
import json
import logging
import time
import urllib.parse

import jwt

from .config import settings

logger = logging.getLogger(__name__)


def _parse_init_data(init_data: str) -> dict:
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    return {k: v for k, v in pairs}


def _check_signature(data: dict, bot_token: str) -> bool:
    received = data.pop("hash", "")
    if _hmac_hex(data.items(), bot_token) == received:
        return True
    # часть клиентов не включает поле signature в data-check-string
    without_sig = {k: v for k, v in data.items() if k != "signature"}
    return _hmac_hex(without_sig.items(), bot_token) == received


def _hmac_hex(items, bot_token: str) -> str:
    check_string = "".join(f"{k}={v}\n" for k, v in sorted(items)).rstrip("\n")
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()


def validate_init_data(init_data: str) -> dict | None:
    data = _parse_init_data(init_data)
    if not data:
        return None
    if not _check_signature(data, settings.bot_token):
        # логируем только имена полей, без значений — по ним видно,
        # шлёт ли клиент то, что мы ожидаем (hash/user/auth_date/…)
        logger.warning("initData signature mismatch; fields=%s", ",".join(sorted(data.keys() - {"user"})))
        return None
    user = json.loads(data.get("user", "{}"))
    return {"tg_id": user.get("id"), "name": user.get("first_name", ""), "username": user.get("username")}


def create_token(tg_id: int, is_admin: bool) -> str:
    return jwt.encode({"tg_id": tg_id, "admin": is_admin, "exp": int(time.time()) + 86400},
                      settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None