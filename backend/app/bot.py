import asyncio
import io
import logging
import time

import qrcode
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, KeyboardButton,
    Message, ReplyKeyboardMarkup, WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import db, vpn
from .config import settings
from .payments import PLANS, get_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

APPS_TEXT = (
    "<b>Приложения для подключения</b>\n"
    "🤖 Android: <b>v2rayNG</b> или NekoBox\n"
    "🍏 iPhone: <b>Streisand</b> или FoXray\n"
    "💻 Windows/macOS: <b>Hiddify</b>, Nekoray или v2rayN\n\n"
    "В приложении выберите «Импорт из буфера обмена» или отсканируйте QR."
)


def fmt_days(user: dict) -> str:
    now = int(time.time())
    if not user["expires_at"]:
        return "нет подписки"
    days = (user["expires_at"] - now) // 86400
    return f"{days} дн." if days > 0 else "истекла"


def lk_text(user: dict) -> str:
    status = "активна" if user["expires_at"] and user["expires_at"] > time.time() and user["server_active"] else "не активна"
    return (
        f"<b>◉ Личный кабинет</b>\n\n"
        f"👤 {user['name'] or 'Пользователь'}\n"
        f"📊 Подписка: {fmt_days(user)} · Статус: {status}\n"
        f"⚙️ Протокол: VLESS · Reality"
    )


def lk_keyboard(user: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⚡ Подключить", callback_data="cfg")
    b.button(text="✨ Тарифы", callback_data="buy")
    b.button(text="📚 Инструкция", callback_data="help")
    b.button(text="💬 Поддержка", callback_data="support")
    if settings.webapp_url:
        b.button(text="📱 Мини-приложение", web_app=WebAppInfo(url=settings.webapp_url))
    b.adjust(2, 2, 1)
    return b.as_markup()


def app_keyboard() -> ReplyKeyboardMarkup | None:
    if not settings.webapp_url:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Личный кабинет", web_app=WebAppInfo(url=settings.webapp_url))]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие…",
    )


def plan_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        b.button(text=f"{plan['name']} — {plan['price']} ₽", callback_data=f"buy:{key}")
    b.button(text="◀️ Назад", callback_data="lk")
    b.adjust(1)
    return b.as_markup()


async def ensure_config(user: dict) -> tuple[str, str | None]:
    """Создать/обновить пользователя в Marzban, вернуть (vless_uri, sub_url)."""
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
    return uri, vpn.subscribe_url(muser.get("subscription_url"))


def qr_bytes(text: str) -> BufferedInputFile:
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return BufferedInputFile(buf.getvalue(), filename="qr.png")


async def notify_admins(text: str, reply_markup: InlineKeyboardMarkup | None = None):
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except Exception:
            logger.exception("admin notify failed")


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = db.get_or_create_user(message.from_user.id, message.from_user.first_name or "", message.from_user.username)
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Быстрый VPN на VLESS + Reality — стабильно работает в России.\n"
        "Ниже — кнопки управления, а «Личный кабинет» открывает приложение.",
        reply_markup=app_keyboard(),
    )
    await message.answer(lk_text(user), reply_markup=lk_keyboard(user))


@router.callback_query(F.data == "lk")
async def cb_lk(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    await callback.message.edit_text(lk_text(user), reply_markup=lk_keyboard(user))
    await callback.answer()


@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery):
    await callback.message.edit_text("✨ Выберите тариф:", reply_markup=plan_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy_plan(callback: CallbackQuery):
    plan = callback.data.split(":", 1)[1]
    if plan not in PLANS:
        return await callback.answer("Неверный тариф")
    user = db.get_user(callback.from_user.id)
    provider = get_provider(settings.payment_provider)
    info = await provider.create(user["id"], PLANS[plan]["price"], plan)
    payment_id = db.create_payment(user["id"], PLANS[plan]["price"], plan, provider.name)
    b = InlineKeyboardBuilder()
    b.button(text="◀️ В личный кабинет", callback_data="lk")
    await callback.message.edit_text(
        f"<b>💳 Оплата</b>\n"
        f"{PLANS[plan]['name']} — {PLANS[plan]['price']} ₽\n\n"
        f"{info.instructions}\n\n"
        f"🧾 Заявка №{payment_id}",
        reply_markup=b.as_markup(),
    )
    await callback.answer()
    await notify_admins(
        f"<b>🧾 Новая заявка №{payment_id}</b>\n"
        f"👤 @{user['username'] or user['tg_id']} (tg_id <code>{user['tg_id']}</code>)\n"
        f"✨ {PLANS[plan]['name']}, {PLANS[plan]['price']} ₽",
        reply_markup=InlineKeyboardBuilder()
        .button(text="✅ Подтвердить", callback_data=f"pay:{payment_id}:ok")
        .button(text="❌ Отклонить", callback_data=f"pay:{payment_id}:no")
        .as_markup(),
    )


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay_decision(callback: CallbackQuery):
    if callback.from_user.id not in settings.admin_ids:
        return await callback.answer("Нет доступа")
    _, payment_id, decision = callback.data.split(":")
    payment_id = int(payment_id)
    payment = db.get_payment(payment_id)
    if not payment or payment["status"] != "pending":
        return await callback.answer("Заявка уже обработана")
    approve = decision == "ok"
    db.set_payment_status(payment_id, "paid" if approve else "cancelled")
    user = db.get_user_by_id(payment["user_id"])
    if approve:
        plan = PLANS[payment["plan"]]
        db.extend_user(user["tg_id"], plan["days"])
        try:
            await ensure_config(db.get_user(user["tg_id"]))
            await vpn.renew_user(vpn.marzban_username(user["tg_id"]), plan["days"])
        except Exception:
            logger.exception("marzban activate failed")
            await notify_admins(f"⚠️ Marzban не активировал пользователя tg_id {user['tg_id']} — проверьте вручную.")
        await callback.message.edit_text(f"✅ Заявка №{payment_id} подтверждена.")
        await bot.send_message(user["tg_id"],
                               f"🎉 Оплата подтверждена! Подписка «{plan['name']}» активна.",
                               reply_markup=lk_keyboard(db.get_user(user['tg_id'])))
    else:
        await callback.message.edit_text(f"❌ Заявка №{payment_id} отклонена.")
        await bot.send_message(user["tg_id"], "Оплата отклонена. Напишите в поддержку.",
                               reply_markup=lk_keyboard(user))
    await callback.answer()


@router.callback_query(F.data == "cfg")
async def cb_cfg(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    b = InlineKeyboardBuilder()
    b.button(text="📷 QR-код", callback_data="cfg:qr")
    b.button(text="🔗 Ссылка vless://", callback_data="cfg:uri")
    b.button(text="📥 Подписочная ссылка", callback_data="cfg:sub")
    b.button(text="♻️ Перевыпустить", callback_data="cfg:regen")
    b.button(text="◀️ Назад", callback_data="lk")
    b.adjust(2, 1, 2)
    text = "⚡ <b>Подключение</b>\n\nИмпортируйте конфиг в приложение одним из способов:"
    if user and not user["uuid"]:
        try:
            await ensure_config(user)
        except Exception as e:
            text = f"Не удалось создать конфиг: {e}"
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data == "cfg:qr")
async def cb_cfg_qr(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    uri, _ = await ensure_config(user)
    await callback.message.answer_photo(qr_bytes(uri), caption="📷 Отсканируйте QR: v2rayNG ▸ «+» ▸ Scan QR.")
    await callback.answer()


@router.callback_query(F.data == "cfg:uri")
async def cb_cfg_uri(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    uri, _ = await ensure_config(user)
    await callback.message.answer(
        "🔗 Скопируйте ссылку и в приложении: «+» → Import from clipboard:\n\n"
        f"<code>{uri}</code>"
    )
    await callback.answer()


@router.callback_query(F.data == "cfg:sub")
async def cb_cfg_sub(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    _, sub = await ensure_config(user)
    if not sub:
        await callback.answer("Подписочные ссылки временно недоступны", show_alert=True)
        return
    await callback.message.answer(
        "📥 Добавьте эту ссылку как подписку в приложении "
        "(v2rayNG ▸ Subscriptions ▸ «+»; Streisand ▸ «+» ▸ Add subscription):\n\n"
        f"<code>{sub}</code>\n\n"
        "Подписка автоматически содержит актуальный конфиг и обновляется.",
    )
    await callback.answer()


@router.callback_query(F.data == "cfg:regen")
async def cb_cfg_regen(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    mb_name = vpn.marzban_username(user["tg_id"])
    await vpn.delete_user(mb_name)
    expire_days = max(1, ((user["expires_at"] or 0) - int(time.time())) // 86400 + 1)
    muser = await vpn.create_user(mb_name, expire_days)
    uri = vpn.build_vless_uri(muser["proxies"]["vless"]["id"], f"user{user['tg_id']}")
    db.save_config(user["tg_id"], mb_name, muser["proxies"]["vless"]["id"], uri)
    await callback.message.edit_text("♻️ Конфиг перевыпущен. Старый больше не работает — подключитесь заново.")
    await callback.answer("Готово")


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    await callback.message.answer(
        "<b>📚 Как подключиться</b>\n\n"
        "1️⃣ Установите приложение (список ниже)\n"
        "2️⃣ «Мой конфиг» → QR или скопируйте vless://\n"
        "3️⃣ Включите VPN в приложении\n\n" + APPS_TEXT +
        "\n\n🇷🇺 Российские сайты работают напрямую, остальное — через VPN. "
        "Обход блокировок обеспечивается протоколом VLESS + Reality."
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery):
    admin = settings.admin_ids[0] if settings.admin_ids else None
    if admin:
        try:
            chat = await bot.get_chat(admin)
            await callback.message.answer(f"💬 Напишите администратору: @{chat.username or admin}")
        except Exception:
            await callback.message.answer("Поддержка скоро будет доступна.")
    await callback.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in settings.admin_ids:
        return
    s = db.stats()
    await message.answer(
        f"<b>📊 Статистика</b>\n"
        f"👥 Пользователей: {s['users']}\n"
        f"✅ Активных подписок: {s['active']}\n"
        f"💰 Оплат: {s['paid_count']}, сумма: {s['revenue']} ₽"
    )


@router.message(Command("extend"))
async def cmd_extend(message: Message):
    if message.from_user.id not in settings.admin_ids:
        return
    args = message.text.split()
    if len(args) != 3:
        return await message.answer("Использование: /extend &lt;tg_id&gt; &lt;дней&gt;")
    tg_id, days = int(args[1]), int(args[2])
    user = db.get_user(tg_id)
    if not user:
        return await message.answer("Пользователь не найден")
    db.extend_user(tg_id, days)
    try:
        await ensure_config(db.get_user(tg_id))
        await vpn.renew_user(vpn.marzban_username(tg_id), days)
    except Exception:
        logger.exception("marzban renew failed")
    await message.answer(f"@{user['username'] or tg_id}: +{days} дн.")
    await bot.send_message(tg_id, f"🎉 Подписка продлена на {days} дн.", reply_markup=lk_keyboard(db.get_user(tg_id)))


@router.message(Command("revoke"))
async def cmd_revoke(message: Message):
    if message.from_user.id not in settings.admin_ids:
        return
    args = message.text.split()
    if len(args) != 2:
        return await message.answer("Использование: /revoke &lt;tg_id&gt;")
    tg_id = int(args[1])
    user = db.get_user(tg_id)
    if not user:
        return await message.answer("Пользователь не найден")
    await vpn.set_status(vpn.marzban_username(tg_id), "disabled")
    db.set_server_active(tg_id, False)
    await message.answer(f"Доступ @{user['username'] or tg_id} отозван.")


async def expiry_loop():
    """Marzban сам отключает пользователей по expire; здесь только флаги в БД."""
    while True:
        try:
            for user in db.get_expired_active():
                db.set_server_active(user["tg_id"], False)
                logger.info("expired: %s", user["tg_id"])
        except Exception:
            logger.exception("expiry loop error")
        await asyncio.sleep(3600)


async def main():
    db.init_db()
    asyncio.create_task(expiry_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
