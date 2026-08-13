import asyncio
import io
import logging
import time

import qrcode
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
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

SUPPORT_HINT = "Поддержка: напишите администратору — @{admin}"


def fmt_days(user: dict) -> str:
    now = int(time.time())
    if not user["expires_at"]:
        return "нет подписки"
    days = (user["expires_at"] - now) // 86400
    return f"{days} дн." if days > 0 else "истекла"


def lk_text(user: dict) -> str:
    status = "активна" if user["expires_at"] and user["expires_at"] > time.time() and user["server_active"] else "не активна"
    return (
        f"<b>Личный кабинет</b>\n\n"
        f"Подписка: {fmt_days(user)}\n"
        f"Статус: {status}\n"
        f"Конфиг: {'создан' if user['uuid'] else 'не создан'}"
    )


def lk_keyboard(user: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Купить подписку", callback_data="buy")
    b.button(text="Мой конфиг", callback_data="cfg")
    b.button(text="Инструкция", callback_data="help")
    b.button(text="Поддержка", callback_data="support")
    if settings.webapp_url:
        b.button(text="Открыть Mini App", url=settings.webapp_url)
    b.adjust(1)
    return b.as_markup()


def plan_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        b.button(text=f"{plan['name']} — {plan['price']} ₽", callback_data=f"buy:{key}")
    b.button(text="Назад", callback_data="lk")
    b.adjust(1)
    return b.as_markup()


def ensure_config(user: dict) -> tuple[str, str]:
    if user["uuid"]:
        return user["config_json"], user["config_uri"]
    uuid = vpn.new_uuid()
    config_json, config_uri = vpn.build_client(uuid, f"user{user['tg_id']}")
    vpn.add_user(uuid)
    db.save_config(user["tg_id"], uuid, config_json, config_uri)
    return config_json, config_uri


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
    await message.answer(lk_text(user), reply_markup=lk_keyboard(user))


@router.callback_query(F.data == "lk")
async def cb_lk(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    await callback.message.edit_text(lk_text(user), reply_markup=lk_keyboard(user))
    await callback.answer()


@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery):
    await callback.message.edit_text("Выберите тариф:", reply_markup=plan_keyboard())
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
    b.button(text="Вернуться в ЛК", callback_data="lk")
    await callback.message.edit_text(
        f"<b>Оплата: {PLANS[plan]['name']} — {PLANS[plan]['price']} ₽</b>\n\n{info.instructions}\n\n"
        f"Номер заявки: #{payment_id}",
        reply_markup=b.as_markup(),
    )
    await callback.answer()
    await notify_admins(
        f"<b>Новая заявка на оплату #{payment_id}</b>\n"
        f"Пользователь: @{user['username'] or user['tg_id']} (tg_id {user['tg_id']})\n"
        f"Тариф: {PLANS[plan]['name']}, {PLANS[plan]['price']} ₽",
        reply_markup=InlineKeyboardBuilder()
        .button(text="Подтвердить", callback_data=f"pay:{payment_id}:ok")
        .button(text="Отклонить", callback_data=f"pay:{payment_id}:no")
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
        if user["uuid"] and not user["server_active"]:
            vpn.add_user(user["uuid"])
            db.set_server_active(user["tg_id"], True)
        await callback.message.edit_text(f"Заявка #{payment_id} подтверждена. {plan['name']} добавлен.")
        await bot.send_message(user["tg_id"], f"✅ Оплата подтверждена! Подписка {plan['name']} активна.",
                               reply_markup=lk_keyboard(user))
    else:
        await callback.message.edit_text(f"Заявка #{payment_id} отклонена.")
        await bot.send_message(user["tg_id"], "❌ Оплата отклонена. Обратитесь в поддержку.",
                               reply_markup=lk_keyboard(user))
    await callback.answer()


@router.callback_query(F.data == "cfg")
async def cb_cfg(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user["uuid"]:
        ensure_config(user)
    b = InlineKeyboardBuilder()
    b.button(text="QR-код (Android/iOS)", callback_data="cfg:qr")
    b.button(text="Файл конфига (Windows)", callback_data="cfg:file")
    b.button(text="Ссылка vless://", callback_data="cfg:uri")
    b.button(text="Перегенерировать", callback_data="cfg:regen")
    b.button(text="Назад", callback_data="lk")
    b.adjust(1)
    await callback.message.edit_text("Ваш конфиг готов. Выберите способ установки:", reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data == "cfg:qr")
async def cb_cfg_qr(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    _, uri = ensure_config(user)
    await callback.message.answer_photo(qr_bytes(uri), caption="Отсканируйте QR в приложении sing-box (Android/iOS).")
    await callback.answer()


@router.callback_query(F.data == "cfg:file")
async def cb_cfg_file(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    config_json, _ = ensure_config(user)
    await callback.message.answer_document(
        BufferedInputFile(config_json.encode(), filename=f"config-{user['tg_id']}.json"),
        caption="Импортируйте файл в приложение (sing-box GUI / Nekoray / v2rayN).",
    )
    await callback.answer()


@router.callback_query(F.data == "cfg:uri")
async def cb_cfg_uri(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    _, uri = ensure_config(user)
    await callback.message.answer(f"<code>{uri}</code>")
    await callback.answer()


@router.callback_query(F.data == "cfg:regen")
async def cb_cfg_regen(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if user["uuid"]:
        vpn.del_user(user["uuid"])
    uuid = vpn.new_uuid()
    config_json, config_uri = vpn.build_client(uuid, f"user{user['tg_id']}")
    vpn.add_user(uuid)
    db.save_config(user["tg_id"], uuid, config_json, config_uri)
    await callback.message.edit_text("Конфиг перегенерирован. Старый перестанет работать.")
    await callback.answer()


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    await callback.message.answer(
        "<b>Инструкция</b>\n\n"
        "1. Скачайте приложение sing-box на устройство.\n"
        "2. Импортируйте конфиг из меню «Мой конфиг» (QR для Android/iOS, файл для Windows).\n"
        "3. Включите VPN-режим.\n\n"
        "<b>Приложения</b>\n"
        "Windows: sing-box GUI / Nekoray / v2rayN (sing-box core)\n"
        "Android: sing-box (SFA) / NekoBox\n"
        "iOS: sing-box (SFI) / Streisand\n\n"
        "Российские сайты идут напрямую (ваш IP), остальные — через VPN. "
        "Списки правил обновляются автоматически."
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery):
    admin = settings.admin_ids[0] if settings.admin_ids else None
    if admin:
        try:
            chat = await bot.get_chat(admin)
            await callback.message.answer(f"Напишите администратору: @{chat.username or admin}")
        except Exception:
            await callback.message.answer("Поддержка скоро будет доступна.")
    await callback.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in settings.admin_ids:
        return
    s = db.stats()
    await message.answer(
        f"<b>Статистика</b>\n"
        f"Пользователей: {s['users']}\n"
        f"Активных подписок: {s['active']}\n"
        f"Оплат: {s['paid_count']}, сумма: {s['revenue']} ₽"
    )


@router.message(Command("extend"))
async def cmd_extend(message: Message):
    if message.from_user.id not in settings.admin_ids:
        return
    args = message.text.split()
    if len(args) != 3:
        return await message.answer("Использование: /extend <tg_id> <дней>")
    tg_id, days = int(args[1]), int(args[2])
    user = db.get_user(tg_id)
    if not user:
        return await message.answer("Пользователь не найден")
    db.extend_user(tg_id, days)
    if user["uuid"] and not user["server_active"]:
        vpn.add_user(user["uuid"])
        db.set_server_active(tg_id, True)
    await message.answer(f"@{user['username'] or tg_id}: +{days} дн. Подписка: {fmt_days(user)}")
    await bot.send_message(tg_id, f"🎉 Подписка продлена на {days} дн.", reply_markup=lk_keyboard(user))


@router.message(Command("revoke"))
async def cmd_revoke(message: Message):
    if message.from_user.id not in settings.admin_ids:
        return
    args = message.text.split()
    if len(args) != 2:
        return await message.answer("Использование: /revoke <tg_id>")
    tg_id = int(args[1])
    user = db.get_user(tg_id)
    if not user:
        return await message.answer("Пользователь не найден")
    if user["uuid"]:
        vpn.del_user(user["uuid"])
        db.set_server_active(tg_id, False)
    await message.answer(f"Доступ @{user['username'] or tg_id} отозван.")


async def expiry_loop():
    while True:
        try:
            for user in db.get_expired_active():
                if user["uuid"]:
                    vpn.del_user(user["uuid"])
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