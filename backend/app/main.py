import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, vpn
from .config import settings
from .payments import PLANS, get_provider
from .webapp_auth import create_token, decode_token, validate_init_data

app = FastAPI(title="VPN backend")


def _auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "no token")
    payload = decode_token(auth[7:])
    if not payload:
        raise HTTPException(401, "bad token")
    return payload


def _admin(payload: dict):
    if not payload.get("admin"):
        raise HTTPException(403, "admin only")


@app.post("/api/webapp/auth")
async def webapp_auth(body: dict):
    user = validate_init_data(body.get("init_data", ""))
    if not user or not user["tg_id"]:
        raise HTTPException(400, "invalid init_data")
    db.get_or_create_user(user["tg_id"], user["name"], user["username"])
    is_admin = user["tg_id"] in settings.admin_ids
    return {"token": create_token(user["tg_id"], is_admin), "admin": is_admin}


@app.get("/api/me")
async def me(request: Request):
    payload = _auth(request)
    user = db.get_user(payload["tg_id"])
    if not user:
        raise HTTPException(404, "user not found")
    now = int(time.time())
    days_left = max(0, (user["expires_at"] or 0) - now) // 86400 if user["expires_at"] else 0
    return {
        "name": user["name"],
        "tg_id": user["tg_id"],
        "expires_at": user["expires_at"],
        "days_left": days_left,
        "active": bool(user["expires_at"] and user["expires_at"] > now and user["server_active"]),
        "has_config": bool(user["uuid"]),
        "plans": PLANS,
        "server": vpn.server_info(),
    }


@app.get("/api/config")
async def get_config(request: Request):
    payload = _auth(request)
    user = db.get_user(payload["tg_id"])
    if not user or not user["config_json"]:
        raise HTTPException(404, "no config")
    return {"config_json": user["config_json"], "config_uri": user["config_uri"]}


@app.post("/api/config/regenerate")
async def regenerate_config(request: Request):
    payload = _auth(request)
    user = db.get_user(payload["tg_id"])
    if not user:
        raise HTTPException(404, "user not found")
    if user["uuid"]:
        vpn.del_user(user["uuid"])
    uuid = vpn.new_uuid()
    config_json, config_uri = vpn.build_client(uuid, f"user{payload['tg_id']}")
    vpn.add_user(uuid)
    db.save_config(payload["tg_id"], uuid, config_json, config_uri)
    return {"config_json": config_json, "config_uri": config_uri}


@app.post("/api/pay")
async def create_payment(request: Request, body: dict):
    payload = _auth(request)
    plan = body.get("plan")
    if plan not in PLANS:
        raise HTTPException(400, "bad plan")
    user = db.get_user(payload["tg_id"])
    if not user:
        raise HTTPException(404, "user not found")
    provider = get_provider(settings.payment_provider)
    info = await provider.create(user["id"], PLANS[plan]["price"], plan)
    payment_id = db.create_payment(user["id"], PLANS[plan]["price"], plan, provider.name)
    return {"payment_id": payment_id, "status": info.status, "instructions": info.instructions}


@app.get("/api/instructions")
async def instructions():
    return {"text": INSTRUCTIONS}


@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    payload = _auth(request)
    _admin(payload)
    return db.stats()


@app.get("/api/admin/payments")
async def admin_payments(request: Request):
    payload = _auth(request)
    _admin(payload)
    return {"payments": db.list_payments()}


@app.post("/api/admin/pay")
async def admin_pay(request: Request, body: dict):
    payload = _auth(request)
    _admin(payload)
    return _confirm_payment(body.get("payment_id"), bool(body.get("approve", True)))


def _confirm_payment(payment_id, approve: bool):
    payment = db.get_payment(payment_id)
    if not payment or payment["status"] != "pending":
        raise HTTPException(400, "bad payment")
    db.set_payment_status(payment_id, "paid" if approve else "cancelled")
    return {"ok": True, "approved": approve, "user_id": payment["user_id"]}


@app.post("/api/admin/extend")
async def admin_extend(request: Request, body: dict):
    payload = _auth(request)
    _admin(payload)
    ok = db.extend_user(body.get("tg_id"), int(body.get("days", 0)))
    if not ok:
        raise HTTPException(404, "user not found")
    return {"ok": True}


INSTRUCTIONS = (
    "1. Скачайте приложение sing-box на своё устройство.\n"
    "2. Откройте профиль из личного кабинета (файл или QR-код).\n"
    "3. Включите VPN-режим в приложении.\n\n"
    "Windows: sing-box GUI / Nekoray / v2rayN (sing-box core)\n"
    "Android: sing-box (SFA) или NekoBox\n"
    "iOS: sing-box (SFI) или Streisand\n\n"
    "Российские сайты работают напрямую, остальные — через VPN. "
    "Подключение автоматически обновляет списки правил раз в сутки."
)


@app.get("/")
async def index():
    dist = Path(__file__).parent / "webapp" / "dist"
    if (dist / "index.html").exists():
        return FileResponse(dist / "index.html")
    return JSONResponse({"ok": True, "webapp": "not built"})


if (Path(__file__).parent / "webapp" / "dist").exists():
    app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "webapp" / "dist" / "assets"), name="assets")
    app.mount("/webapp", StaticFiles(directory=Path(__file__).parent / "webapp" / "dist", html=True), name="webapp")