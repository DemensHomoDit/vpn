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
WEBAPP_DIST = Path(__file__).parent.parent / "webapp" / "dist"

INSTRUCTIONS = (
    "1. Установите Happ — рекомендуемое приложение.\n"
    "   Android: github.com/Happ-proxy/happ-android/releases\n"
    "   iPhone: App Store — «Happ — Proxy Utility»\n"
    "   Windows/macOS: github.com/Happ-proxy/happ-desktop/releases\n"
    "2. Во вкладке «Конфиг» отсканируйте QR или скопируйте ссылку vless://.\n"
    "3. В Happ: «+» → вставить ссылку / сканировать QR.\n"
    "4. Включите тумблер VPN в Happ.\n\n"
    "Лучше добавить подписочную ссылку (вкладка «Конфиг» → «Скопировать подписку»):\n"
    "конфиг будет обновляться сам.\n\n"
    "Также подходят: v2rayNG (Android), Streisand (iOS), Nekoray, v2rayN.\n"
    "Российские сайты идут напрямую (ваш IP), остальные — через VPN.\n"
    "Протокол VLESS + Reality имитирует обычный HTTPS-трафик к dl.google.com."
)


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


_sub_cache: dict[int, str] = {}


async def _ensure_cfg(user: dict) -> tuple[str, str | None]:
    mb_name = vpn.marzban_username(user["tg_id"])
    muser = await vpn.get_user(mb_name)
    if not muser or not muser.get("proxies", {}).get("vless", {}).get("id"):
        if muser:
            await vpn.delete_user(mb_name)
        days = max(1, ((user["expires_at"] or 0) - int(time.time())) // 86400 + 1)
        muser = await vpn.create_user(mb_name, days)
    uuid = muser["proxies"]["vless"]["id"]
    uri = vpn.build_vless_uri(uuid, f"user{user['tg_id']}")
    db.save_config(user["tg_id"], mb_name, uuid, uri)
    sub = vpn.subscribe_url(muser.get("subscription_url"))
    if sub:
        _sub_cache[user["tg_id"]] = sub
    return uri, sub


@app.get("/api/config")
async def get_config(request: Request):
    payload = _auth(request)
    user = db.get_user(payload["tg_id"])
    if not user:
        raise HTTPException(404, "user not found")
    uri, sub = await _ensure_cfg(user)
    return {"config_uri": uri, "config_json": "", "subscribe_url": sub}


@app.post("/api/config/regenerate")
async def regenerate_config(request: Request):
    payload = _auth(request)
    user = db.get_user(payload["tg_id"])
    if not user:
        raise HTTPException(404, "user not found")
    await vpn.delete_user(vpn.marzban_username(payload["tg_id"]))
    uri, sub = await _ensure_cfg(user)
    return {"config_uri": uri, "config_json": "", "subscribe_url": sub}


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
    approved = bool(body.get("approve", True))
    payment = db.get_payment(body.get("payment_id"))
    result = _confirm_payment(body.get("payment_id"), approved)
    if approved and payment and payment["status"] == "pending":
        urow = db.get_user_by_id(payment["user_id"])
        if urow:
            plan = PLANS.get(payment["plan"], {"days": 30})
            db.extend_user(urow["tg_id"], plan["days"])
            try:
                await _ensure_cfg(db.get_user(urow["tg_id"]))
                await vpn.renew_user(vpn.marzban_username(urow["tg_id"]), plan["days"])
            except Exception:
                pass
    return result


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
    try:
        tg_id = int(body["tg_id"])
        days = int(body.get("days", 0))
        await _ensure_cfg(db.get_user(tg_id))
        await vpn.renew_user(vpn.marzban_username(tg_id), days)
    except Exception:
        pass
    return {"ok": True}


@app.get("/")
async def index():
    if (WEBAPP_DIST / "index.html").exists():
        return FileResponse(WEBAPP_DIST / "index.html")
    return JSONResponse({"ok": True, "webapp": "not built"})


if WEBAPP_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEBAPP_DIST / "assets"), name="assets")
    app.mount("/webapp", StaticFiles(directory=WEBAPP_DIST, html=True), name="webapp")
