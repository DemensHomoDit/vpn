"""Клиент Marzban REST API: создание/продление/удаление пользователей VLESS."""
import time
import urllib.parse
import uuid as uuidlib

import httpx

from .config import settings

_token: str | None = None
_client = httpx.AsyncClient(base_url=settings.marzban_url, timeout=20)


class MarzbanError(RuntimeError):
    pass


def marzban_username(tg_id: int) -> str:
    return f"u{tg_id}"


def new_uuid() -> str:
    return str(uuidlib.uuid4())


async def _login() -> str:
    global _token
    res = await _client.post(
        "/api/admin/token",
        data={"username": settings.marzban_username, "password": settings.marzban_password},
    )
    if res.status_code != 200:
        raise MarzbanError(f"login failed ({res.status_code}): {res.text[:200]}")
    _token = res.json()["access_token"]
    return _token


async def _request(method: str, path: str, json_body: dict | None = None) -> httpx.Response:
    token = _token or await _login()
    res = await _client.request(method, path, json=json_body,
                                headers={"Authorization": f"Bearer {token}"})
    if res.status_code == 401:
        await _login()
        res = await _client.request(method, path, json=json_body,
                                    headers={"Authorization": f"Bearer {_token}"})
    return res


async def get_user(username: str) -> dict | None:
    res = await _request("GET", f"/api/user/{username}")
    return res.json() if res.status_code == 200 else None


async def create_user(username: str, days: int) -> dict:
    body = {
        "username": username,
        "status": "active",
        "expire": int(time.time()) + days * 86400,
        "inbounds": {"vless": [settings.inbound_tag]},
        "proxies": {"vless": {"flow": "xtls-rprx-vision"}},
    }
    res = await _request("POST", "/api/user", body)
    if res.status_code != 200:
        raise MarzbanError(f"create failed ({res.status_code}): {res.text[:200]}")
    return res.json()


async def renew_user(username: str, days: int) -> dict:
    """Продлить подписку от максимума из (текущего expire, сейчас)."""
    user = await get_user(username)
    if not user:
        raise MarzbanError(f"{username} not found")
    now = int(time.time())
    base = max(user.get("expire") or 0, now)
    res = await _request("PUT", f"/api/user/{username}",
                         {"expire": base + days * 86400, "status": "active"})
    if res.status_code != 200:
        raise MarzbanError(f"renew failed ({res.status_code}): {res.text[:200]}")
    return res.json()


async def set_status(username: str, status: str) -> dict:
    res = await _request("PUT", f"/api/user/{username}", {"status": status})
    if res.status_code != 200:
        raise MarzbanError(f"set status failed ({res.status_code}): {res.text[:200]}")
    return res.json()


async def delete_user(username: str):
    await _request("DELETE", f"/api/user/{username}")


def build_vless_uri(uuid: str, name: str) -> str:
    params = {
        "security": "reality",
        "type": "tcp",
        "flow": "xtls-rprx-vision",
        "sni": settings.reality_sni,
        "fp": "chrome",
        "pbk": settings.reality_pbk,
        "sid": settings.reality_sid,
    }
    query = urllib.parse.urlencode(params)
    label = urllib.parse.quote(f"VPN • {name}")
    return f"vless://{uuid}@{settings.vps_ip}:{settings.vps_port}?{query}#{label}"


def subscribe_url(sub_path: str | None) -> str | None:
    if not sub_path or not settings.marzban_public_url:
        return None
    return settings.marzban_public_url + sub_path


def server_info() -> dict:
    return {
        "ip": settings.vps_ip,
        "port": settings.vps_port,
        "sni": settings.reality_sni,
    }
