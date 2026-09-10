from __future__ import annotations

import asyncio
import html
import json
import logging
import shutil
import tempfile
from pathlib import Path

from aiogram import BaseMiddleware, F, Router, Bot
from aiogram.filters import CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, FSInputFile, ReplyKeyboardRemove

from config import Settings
from db import Database
from keyboards import MENU_DEFAULTS, admin_menu, back_menu, button, copy_button, grid, main_menu
from states import AdminState, BackupState, BroadcastState, CardState, ChannelState, EditCardState, EditProductState, MenuButtonState, OwnerReplyState, ProductState, ShopNameState, SupportState
from aiogram.enums import ButtonStyle, ChatMemberStatus
from web_panel import create_access

router = Router()
logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        db = data.get("db")
        user = getattr(event, "from_user", None)
        if db and user and await db.is_blocked(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("دسترسی شما مسدود است.", show_alert=True)
            else:
                await event.answer("دسترسی شما مسدود است.")
            return None
        if isinstance(event, CallbackQuery) and db and user:
            admin_callbacks = (
                "admin", "admin_", "add_product", "edit_product:", "delete_product:", "toggle_product:",
                "add_card", "edit_card:", "delete_card:", "toggle_card:", "add_admin", "delete_admin:",
                "admin_admins", "admin_block", "toggle_block:", "admin_channels", "add_channel", "delete_channel:",
                "admin_backup", "download_backup", "restore_backup", "toggle_ui_mode", "customize_menu", "edit_menu:", "reset_menu",
            )
            if any((event.data or "").startswith(prefix) for prefix in admin_callbacks):
                settings = data.get("settings")
                if settings and not await is_admin(db, user.id, settings):
                    await event.answer("دسترسی مدیریت ندارید.", show_alert=True)
                    return None
        return await handler(event, data)


router.message.middleware(SecurityMiddleware())
router.callback_query.middleware(SecurityMiddleware())


class ConfiguredMenuFilter(Filter):
    async def __call__(self, message: Message, db: Database) -> bool:
        config = await load_menu_config(db)
        return bool(message.text and any(item["label"] == message.text for item in config.values()))

def is_owner(user_id: int, settings: Settings) -> bool:
    return user_id == settings.owner_id

async def is_admin(db: Database, user_id: int, settings: Settings, permission: str | None = None) -> bool:
    if is_owner(user_id, settings):
        return True
    row = await db.fetchone("SELECT permissions FROM admins WHERE user_id=?", (user_id,))
    return bool(row and (permission is None or permission in row[0].split(",")))


async def shop_name(db: Database, settings: Settings) -> str:
    return await db.get_setting("shop_name", settings.shop_name)


async def load_menu_config(db: Database) -> dict:
    raw = await db.get_setting("menu_config", "")
    if not raw:
        return {key: value.copy() for key, value in MENU_DEFAULTS.items()}
    try:
        saved = json.loads(raw)
        config = {key: value.copy() for key, value in MENU_DEFAULTS.items()}
        for key in config:
            if key in saved:
                config[key].update(saved[key])
        orders = [item["order"] for item in config.values()]
        if (
            len(set(orders)) != len(config)
            or sorted(orders) != list(range(1, len(config) + 1))
            or any(item["color"] not in {"danger", "success", "primary"} for item in config.values())
            or any(not isinstance(item["label"], str) or not 1 <= len(item["label"]) <= 40 for item in config.values())
        ):
            return {key: value.copy() for key, value in MENU_DEFAULTS.items()}
        return config
    except (json.JSONDecodeError, TypeError, ValueError):
        return {key: value.copy() for key, value in MENU_DEFAULTS.items()}


async def save_menu_config(db: Database, config: dict) -> None:
    await db.set_setting("menu_config", json.dumps(config, ensure_ascii=False))

async def safe_edit(call: CallbackQuery, text: str, markup=None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:
        await call.message.answer(text, reply_markup=markup)


async def subscription_markup(db: Database, bot: Bot) -> InlineKeyboardMarkup | None:
    rows = await db.fetchall("SELECT * FROM channels WHERE is_active=1")
    buttons = []
    for row in rows:
        if row["invite_link"]:
            buttons.append([InlineKeyboardButton(text=f"عضویت در {row['title']}", url=row["invite_link"])])
    if not buttons:
        return None
    buttons.append([InlineKeyboardButton(text="✅ بررسی عضویت", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def is_subscribed(user_id: int, db: Database, bot: Bot) -> bool:
    rows = await db.fetchall("SELECT chat_id FROM channels WHERE is_active=1")
    for row in rows:
        try:
            member = await bot.get_chat_member(row["chat_id"], user_id)
            if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
                return False
        except Exception:
            return False
    return True

async def profile_text(user_id: int, db: Database) -> str:
    row = await db.fetchone("SELECT * FROM users WHERE id=?", (user_id,))
    if row is None:
        return "👤 هنوز اطلاعاتی برای شما ثبت نشده است. ابتدا /start را بزنید."
    count = await db.fetchone("SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE user_id=?", (user_id,))
    return (
        f"👤 مشخصات شما\n\n"
        f"نام: {html.escape(row['full_name'])}\n"
        f"نام کاربری: @{html.escape(row['username'] or 'ندارد')}\n"
        f"شناسه: <code>{row['id']}</code>\n"
        f"تعداد کالا در سبد: {count[0]}"
    )


async def present_main_menu(message: Message, db: Database, settings: Settings, user_id: int, text: str) -> None:
    mode = await db.get_setting("ui_mode", "keyboard")
    markup = main_menu(await is_admin(db, user_id, settings), mode, await load_menu_config(db))
    if mode == "glass":
        await message.answer("منوی قدیمی بسته شد.", reply_markup=ReplyKeyboardRemove())
    await message.answer(text, reply_markup=markup)

async def home(message: Message, db: Database, settings: Settings, bot: Bot) -> None:
    if not await is_subscribed(message.from_user.id, db, bot):
        markup = await subscription_markup(db, bot)
        if markup:
            await message.answer("برای استفاده از فروشگاه ابتدا در کانال‌های زیر عضو شوید:", reply_markup=markup)
        return
    admin = await is_admin(db, message.from_user.id, settings)
    await present_main_menu(
        message, db, settings, message.from_user.id,
        f"✨ <b>{html.escape(await shop_name(db, settings))}</b>\n\nانتخاب کنید و خریدتان را سریع شروع کنید.",
    )

@router.message(CommandStart())
async def start(message: Message, db: Database, settings: Settings, bot: Bot) -> None:
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if await db.is_blocked(message.from_user.id):
        await message.answer("دسترسی شما به این فروشگاه مسدود شده است.")
        return
    await home(message, db, settings, bot)


@router.callback_query(F.data == "check_subscription")
async def check_subscription(call: CallbackQuery, db: Database, bot: Bot, settings: Settings) -> None:
    if not await is_subscribed(call.from_user.id, db, bot):
        await call.answer("هنوز عضویت شما تأیید نشده است.", show_alert=True)
        return
    await call.answer("عضویت تأیید شد ✅")
    await present_main_menu(
        call.message, db, settings, call.from_user.id,
        f"✨ <b>{html.escape(await shop_name(db, settings))}</b>\n\nمنوی اصلی را انتخاب کنید.",
    )


@router.message(F.text == "👤 مشخصات من")
async def profile_button(message: Message, db: Database, bot: Bot) -> None:
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if not await is_subscribed(message.from_user.id, db, bot):
        markup = await subscription_markup(db, bot)
        if markup:
            await message.answer("برای استفاده از این بخش ابتدا عضویت خود را کامل کنید:", reply_markup=markup)
        return
    await message.answer(await profile_text(message.from_user.id, db), reply_markup=back_menu())


@router.message(F.text == "💬 پشتیبانی")
async def support_button(message: Message, db: Database, bot: Bot, state: FSMContext) -> None:
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if not await is_subscribed(message.from_user.id, db, bot):
        markup = await subscription_markup(db, bot)
        if markup:
            await message.answer("برای استفاده از پشتیبانی ابتدا عضویت خود را کامل کنید:", reply_markup=markup)
        return
    await state.set_state(SupportState.waiting_message)
    await message.answer("💬 پیام خود را بفرستید؛ متن، عکس یا فایل قابل ارسال است.", reply_markup=back_menu())


@router.message(ConfiguredMenuFilter())
async def configured_menu_button(message: Message, db: Database, settings: Settings, state: FSMContext, bot: Bot) -> None:
    config = await load_menu_config(db)
    action = next(key for key, item in config.items() if item["label"] == message.text)
    if action == "products":
        rows = await db.fetchall("SELECT * FROM products WHERE is_active=1 ORDER BY id DESC")
        items = [button(f"{row['name']} | {row['price']:,} تومان", f"product:{row['id']}", ButtonStyle.SUCCESS) for row in rows]
        await message.answer("🛍 محصولات فروشگاه\n\nیک محصول را انتخاب کنید:", reply_markup=grid(items, 1) if items else back_menu())
    elif action == "cart":
        await message.answer("سبد خرید را باز کنید:", reply_markup=grid([button("🧺 نمایش سبد", "cart")], 1))
    elif action == "profile":
        await message.answer(await profile_text(message.from_user.id, db), reply_markup=back_menu())
    elif action == "support":
        await state.set_state(SupportState.waiting_message)
        await message.answer("💬 پیام خود را بفرستید؛ متن، عکس یا فایل قابل ارسال است.", reply_markup=back_menu())
    else:
        text = "📚 راهنمای خرید\n\nمحصول را انتخاب کنید، به سبد اضافه کنید و پرداخت را انجام دهید." if action == "help" else "📜 قوانین\n\nثبت سفارش به معنی پذیرش قوانین فروشگاه است."
        await message.answer(text, reply_markup=back_menu())


@router.message(F.text.in_({"🛍 محصولات", "🧺 سبد خرید", "👤 مشخصات من", "💬 پشتیبانی", "📚 راهنما", "📜 قوانین", "⚙️ مدیریت", "🏠 منوی اصلی"}))
async def reply_menu(message: Message, db: Database, settings: Settings, state: FSMContext, bot: Bot) -> None:
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if not await is_subscribed(message.from_user.id, db, bot):
        markup = await subscription_markup(db, bot)
        if markup:
            await message.answer("برای استفاده از فروشگاه ابتدا عضویت خود را کامل کنید:", reply_markup=markup)
        return
    routes = {
        "🛍 محصولات": "products", "🧺 سبد خرید": "cart", "👤 مشخصات من": "profile",
        "💬 پشتیبانی": "support", "📚 راهنما": "help", "📜 قوانین": "rules",
        "⚙️ مدیریت": "admin", "🏠 منوی اصلی": "home",
    }
    target = routes[message.text]
    if target == "home":
        await state.clear(); await home(message, db, settings, bot); return
    if target == "admin" and not await is_admin(db, message.from_user.id, settings):
        await message.answer("دسترسی مدیریت ندارید."); return
    if target == "admin":
        await message.answer("⚙️ پنل مدیریت\n\nعملیات مورد نظر را انتخاب کنید:", reply_markup=admin_menu()); return
    if target == "products":
        rows = await db.fetchall("SELECT * FROM products WHERE is_active=1 ORDER BY id DESC")
        items = [button(f"{row['name']} | {row['price']:,} تومان", f"product:{row['id']}", ButtonStyle.SUCCESS) for row in rows]
        await message.answer("🛍 محصولات فروشگاه\n\nیک محصول را انتخاب کنید:", reply_markup=grid(items, 1) if items else back_menu()); return
    if target == "cart":
        await message.answer("برای مشاهده سبد خرید، از دکمه‌ی زیر استفاده کنید.", reply_markup=grid([button("🧺 نمایش سبد", "cart", ButtonStyle.PRIMARY)], 1)); return
    if target == "profile":
        await message.answer(await profile_text(message.from_user.id, db), reply_markup=back_menu())
        return
    if target == "support":
        await state.set_state(SupportState.waiting_message); await message.answer("💬 پیام خود را بنویسید:", reply_markup=back_menu()); return
    text = "📚 راهنمای خرید\n\nمحصول را انتخاب کنید، به سبد اضافه کنید، مبلغ را ببینید و رسید پرداخت را برای پشتیبانی ارسال کنید." if target == "help" else "📜 قوانین\n\nثبت سفارش به معنی پذیرش قوانین است. رسید جعلی، مزاحمت و سوءاستفاده باعث مسدودی حساب می‌شود."
    await message.answer(text, reply_markup=back_menu())

@router.callback_query(F.data == "home")
async def home_callback(call: CallbackQuery, db: Database, settings: Settings) -> None:
    await call.answer()
    await present_main_menu(
        call.message, db, settings, call.from_user.id,
        f"✨ <b>{html.escape(await shop_name(db, settings))}</b>\n\nمنوی اصلی را انتخاب کنید.",
    )

@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    await db.upsert_user(call.from_user.id, call.from_user.username, call.from_user.full_name)
    await safe_edit(call, await profile_text(call.from_user.id, db), back_menu())

@router.callback_query(F.data == "products")
async def products(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    rows = await db.fetchall("SELECT * FROM products WHERE is_active=1 ORDER BY id DESC")
    if not rows:
        await safe_edit(call, "📦 هنوز محصولی ثبت نشده است.", back_menu())
        return
    items = [button(f"{row['name']} | {row['price']:,} تومان", f"product:{row['id']}", ButtonStyle.SUCCESS) for row in rows]
    await safe_edit(call, "🛍 محصولات فروشگاه\n\nیک محصول را انتخاب کنید:", grid(items, 1))

@router.callback_query(F.data.startswith("product:"))
async def product_detail(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    product_id = int(call.data.split(":")[1])
    row = await db.fetchone("SELECT * FROM products WHERE id=? AND is_active=1", (product_id,))
    if not row:
        await call.answer("محصول پیدا نشد", show_alert=True)
        return
    text = f"🛒 {html.escape(row['name'])}\n\n{html.escape(row['description'])}\n\nقیمت: {row['price']:,} تومان\nموجودی: {row['stock']} عدد"
    markup = grid([button("➕ افزودن به سبد", f"add:{row['id']}", ButtonStyle.SUCCESS), button("↩️ محصولات", "products")], 1)
    if row["photo_id"]:
        await call.message.answer_photo(row["photo_id"], caption=text, reply_markup=markup)
    else:
        await safe_edit(call, text, markup)

@router.callback_query(F.data.startswith("add:"))
async def add_cart(call: CallbackQuery, db: Database) -> None:
    product_id = int(call.data.split(":")[1])
    if not await db.add_to_cart(call.from_user.id, product_id):
        await call.answer("این محصول موجود نیست", show_alert=True)
        return
    await call.answer("به سبد خرید اضافه شد ✅", show_alert=True)

@router.callback_query(F.data == "cart")
async def cart(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    rows = await db.get_cart(call.from_user.id)
    if not rows:
        await safe_edit(call, "🧺 سبد خرید شما خالی است.", back_menu())
        return
    lines = ["🧺 سبد خرید شما\n"]
    for row in rows:
        lines.append(f"• {row['name']} × {row['quantity']} = {row['price'] * row['quantity']:,} تومان")
    total = await db.cart_total(call.from_user.id)
    lines.append(f"\n💰 مبلغ نهایی: {total:,} تومان")
    markup = grid([button("💳 مشاهده کارت‌های پرداخت", "payment", ButtonStyle.SUCCESS), button("🗑 خالی کردن سبد", "clear_cart", ButtonStyle.DANGER), button("↩️ بازگشت", "home")])
    await safe_edit(call, "\n".join(lines), markup)

@router.callback_query(F.data == "clear_cart")
async def clear_cart(call: CallbackQuery, db: Database) -> None:
    await db.clear_cart(call.from_user.id)
    await call.answer("سبد خالی شد")
    await safe_edit(call, "سبد خرید خالی شد.", back_menu())

@router.callback_query(F.data == "payment")
async def payment(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    cards = await db.fetchall("SELECT * FROM cards WHERE is_active=1")
    total = await db.cart_total(call.from_user.id)
    if not cards:
        await safe_edit(call, "روش پرداخت هنوز تنظیم نشده است.", back_menu("cart"))
        return
    lines = [f"💳 مبلغ قابل پرداخت: {total:,} تومان\n\nشماره کارت‌های پرداخت:"]
    items = []
    for card in cards:
        lines.append(f"\n{html.escape(card['title'])}: <code>{card['number']}</code>\nبه نام: {html.escape(card['holder'])}")
        items.append(copy_button(f"📋 کپی کارت {card['title']}", card['number'], ButtonStyle.PRIMARY))
    items.append(copy_button(f"📋 کپی مبلغ {total:,}", str(total), ButtonStyle.SUCCESS))
    items.append(button("↩️ سبد خرید", "cart"))
    await safe_edit(call, "\n".join(lines) + "\n\nشماره کارت یا مبلغ را برای کپی لمس کنید.", grid(items, 1))

@router.callback_query(F.data.startswith("copy:"))
async def copy_value(call: CallbackQuery) -> None:
    await call.answer(f"برای کپی: {call.data[5:]}", show_alert=True)

@router.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(SupportState.waiting_message)
    await safe_edit(call, "💬 پیام خود را بنویسید؛ به پشتیبانی ارسال می‌شود.", back_menu())

@router.message(SupportState.waiting_message)
async def support_message(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    try:
        support_db = Database(settings.db_path)
        await support_db.execute(
            "INSERT INTO support_messages(user_id,message_id,content,status,created_at) VALUES(?,?,?,?,datetime('now'))",
            (message.from_user.id, message.message_id, message.text or message.caption or "[رسانه]", "open"),
        )
        await bot.send_message(
            settings.owner_id,
            f"📩 پیام پشتیبانی از {html.escape(message.from_user.full_name)} "
            f"(@{html.escape(message.from_user.username or 'ندارد')})\n"
            f"شناسه کاربر: <code>{message.from_user.id}</code>",
            reply_markup=grid([
                button("↩️ پاسخ به کاربر", f"support_reply:{message.from_user.id}", ButtonStyle.SUCCESS),
            ], 1),
        )
        await bot.copy_message(
            chat_id=settings.owner_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception:
        logger.exception("Could not deliver support message from user %s", message.from_user.id)
        await message.answer("ارسال پیام انجام نشد. لطفاً چند لحظه بعد دوباره تلاش کنید.", reply_markup=back_menu())
        return
    await state.clear()
    await message.answer("پیام شما برای پشتیبانی ارسال شد ✅", reply_markup=back_menu())


@router.callback_query(F.data.startswith("support_reply:"))
async def support_reply_start(call: CallbackQuery, state: FSMContext, db: Database, settings: Settings) -> None:
    if not await is_admin(db, call.from_user.id, settings, "support"):
        await call.answer("دسترسی پاسخ‌گویی ندارید.", show_alert=True)
        return
    user_id = int(call.data.split(":", 1)[1])
    await state.update_data(user_id=user_id)
    await state.set_state(OwnerReplyState.waiting_message)
    await call.answer()
    await call.message.answer("✍️ پاسخ خود را بفرستید؛ متن، عکس یا فایل قابل ارسال است.", reply_markup=back_menu("admin"))


@router.message(OwnerReplyState.waiting_message)
async def support_reply_send(message: Message, state: FSMContext, bot: Bot, db: Database, settings: Settings) -> None:
    if not await is_admin(db, message.from_user.id, settings, "support"):
        await state.clear()
        return
    data = await state.get_data()
    try:
        await bot.copy_message(
            chat_id=data["user_id"],
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception:
        logger.exception("Could not deliver support reply to user %s", data.get("user_id"))
        await message.answer("ارسال پاسخ انجام نشد؛ احتمالاً کاربر ربات را مسدود کرده است.")
        return
    await state.clear()
    await message.answer("پاسخ برای کاربر ارسال شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data.in_({"help", "rules"}))
async def info(call: CallbackQuery) -> None:
    await call.answer()
    if call.data == "help":
        text = "📚 راهنمای خرید\n\n۱. از بخش محصولات، کالا را انتخاب کنید.\n۲. آن را به سبد اضافه کنید.\n۳. مبلغ را ببینید و کارت پرداخت را کپی کنید.\n۴. رسید پرداخت را برای پشتیبانی ارسال کنید.\n\nپشتیبانی در تمام مراحل کنار شماست."
    else:
        text = "📜 قوانین و مقررات\n\n• ثبت سفارش به معنی پذیرش قوانین است.\n• مسئولیت واردکردن صحیح اطلاعات پرداخت با خریدار است.\n• سفارش پس از تأیید پرداخت پردازش می‌شود.\n• اطلاعات کاربران نزد فروشگاه محفوظ می‌ماند.\n• در صورت مغایرت، پیش از هر اقدامی با پشتیبانی تماس بگیرید.\n• سوءاستفاده، ارسال رسید جعلی و مزاحمت موجب مسدودی حساب می‌شود."
    await safe_edit(call, text, back_menu())

@router.callback_query(F.data == "admin")
async def admin(call: CallbackQuery, db: Database, settings: Settings) -> None:
    await call.answer()
    if not await is_admin(db, call.from_user.id, settings):
        return
    await safe_edit(call, "⚙️ پنل مدیریت\n\nعملیات مورد نظر را انتخاب کنید:", admin_menu())


@router.callback_query(F.data == "toggle_ui_mode")
async def toggle_ui_mode(call: CallbackQuery, db: Database, settings: Settings) -> None:
    if not await is_admin(db, call.from_user.id, settings):
        await call.answer("دسترسی مدیریت ندارید.", show_alert=True)
        return
    current = await db.get_setting("ui_mode", "keyboard")
    new_mode = "glass" if current == "keyboard" else "keyboard"
    await db.set_setting("ui_mode", new_mode)
    label = "شیشه‌ای رنگی" if new_mode == "glass" else "کیبوردی سریع"
    await call.answer(f"حالت {label} فعال شد ✅", show_alert=True)
    await safe_edit(call, f"🎛 حالت نمایش روی <b>{label}</b> تنظیم شد.\n\nبرای دیدن منوی جدید، منوی اصلی را بزنید.", admin_menu())


@router.callback_query(F.data == "shop_name")
async def shop_name_start(call: CallbackQuery, state: FSMContext, db: Database, settings: Settings) -> None:
    if not is_owner(call.from_user.id, settings):
        await call.answer("تغییر نام فروشگاه فقط برای مالک است.", show_alert=True)
        return
    await state.set_state(ShopNameState.waiting_name)
    await call.answer()
    await safe_edit(call, f"🏷 نام فعلی: <b>{html.escape(await shop_name(db, settings))}</b>\n\nنام جدید فروشگاه را بفرستید:", back_menu("admin"))


@router.message(ShopNameState.waiting_name)
async def shop_name_save(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    if not is_owner(message.from_user.id, settings):
        await state.clear()
        return
    name = (message.text or "").strip()
    if not 2 <= len(name) <= 60:
        await message.answer("نام فروشگاه باید بین ۲ تا ۶۰ کاراکتر باشد.")
        return
    await db.set_setting("shop_name", name)
    await state.clear()
    await message.answer(f"نام فروشگاه به «{html.escape(name)}» تغییر کرد ✅", reply_markup=admin_menu())


@router.callback_query(F.data == "web_panel")
async def web_panel_link(call: CallbackQuery, db: Database, settings: Settings) -> None:
    if not is_owner(call.from_user.id, settings):
        await call.answer("این بخش فقط برای مالک است.", show_alert=True)
        return
    access = create_access(call.from_user.id, settings)
    await call.answer("لینک پنل ساخته شد ✅", show_alert=True)
    await call.message.answer(
        "🌐 <b>پنل وب آماده است</b>\n\n"
        f"لینک ورود: {access['url']}\n"
        f"نام کاربری: <code>{access['username']}</code>\n"
        f"رمز یک‌بارمصرف: <code>{access['password']}</code>\n\n"
        "این اطلاعات تا ۱۵ دقیقه معتبر است و لینک را برای دیگران ارسال نکنید.",
    )


@router.callback_query(F.data == "customize_menu")
async def customize_menu(call: CallbackQuery, db: Database, settings: Settings) -> None:
    if not await is_admin(db, call.from_user.id, settings):
        await call.answer("دسترسی مدیریت ندارید.", show_alert=True)
        return
    config = await load_menu_config(db)
    items = [button(f"{item['label']} | رنگ: {item['color']} | ردیف: {item['order']}", f"edit_menu:{key}") for key, item in sorted(config.items(), key=lambda pair: pair[1]["order"])]
    items += [button("♻️ بازگردانی پیش‌فرض", "reset_menu", ButtonStyle.DANGER), button("↩️ مدیریت", "admin")]
    await call.answer()
    await safe_edit(call, "🖌 شخصی‌سازی منوی اصلی\n\nدکمه‌ای را برای ویرایش انتخاب کنید:", grid(items, 1))


@router.callback_query(F.data.startswith("edit_menu:"))
async def edit_menu_start(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    key = call.data.split(":", 1)[1]
    config = await load_menu_config(db)
    if key not in config:
        await call.answer("دکمه پیدا نشد", show_alert=True)
        return
    await state.update_data(menu_key=key)
    await state.set_state(MenuButtonState.label)
    await call.answer()
    await call.message.answer(f"نام جدید دکمه را بفرستید:\nنام فعلی: {config[key]['label']}")


@router.message(MenuButtonState.label)
async def edit_menu_label(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text) > 40:
        await message.answer("نام دکمه باید بین ۱ تا ۴۰ کاراکتر باشد.")
        return
    await state.update_data(label=message.text)
    await state.set_state(MenuButtonState.color)
    await message.answer("رنگ دکمه را انتخاب کنید:", reply_markup=grid([
        button("🔴 قرمز", "menu_color:danger", ButtonStyle.DANGER),
        button("🟢 سبز", "menu_color:success", ButtonStyle.SUCCESS),
        button("🔵 آبی", "menu_color:primary", ButtonStyle.PRIMARY),
    ]))


@router.callback_query(MenuButtonState.color, F.data.startswith("menu_color:"))
async def edit_menu_color(call: CallbackQuery, state: FSMContext) -> None:
    color = call.data.split(":", 1)[1]
    await state.update_data(color=color)
    await state.set_state(MenuButtonState.order)
    await call.answer()
    await call.message.answer("ترتیب نمایش را با عدد ۱ تا ۶ بفرستید:")


@router.message(MenuButtonState.order)
async def edit_menu_order(message: Message, state: FSMContext, db: Database) -> None:
    if not message.text or not message.text.isdigit() or not 1 <= int(message.text) <= 6:
        await message.answer("ترتیب باید عددی بین ۱ تا ۶ باشد.")
        return
    data = await state.get_data()
    config = await load_menu_config(db)
    key = data["menu_key"]
    config[key].update(label=data["label"], color=data["color"], order=int(message.text))
    await save_menu_config(db, config)
    await state.clear()
    await message.answer("تنظیمات دکمه ذخیره شد ✅", reply_markup=admin_menu())


@router.callback_query(F.data == "reset_menu")
async def reset_menu(call: CallbackQuery, db: Database, settings: Settings) -> None:
    if not await is_admin(db, call.from_user.id, settings):
        await call.answer("دسترسی ندارید.", show_alert=True)
        return
    await save_menu_config(db, {key: value.copy() for key, value in MENU_DEFAULTS.items()})
    await call.answer("منوی اصلی به حالت پیش‌فرض برگشت ✅", show_alert=True)
    await customize_menu(call, db, settings)

@router.callback_query(F.data == "admin_add_product")
async def add_product_start(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer(); await state.set_state(ProductState.name)
    await safe_edit(call, "نام محصول را بفرستید:", back_menu("admin"))

@router.message(ProductState.name)
async def product_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text); await state.set_state(ProductState.description); await message.answer("توضیحات محصول:")

@router.message(ProductState.description)
async def product_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text); await state.set_state(ProductState.price); await message.answer("قیمت به تومان:")

@router.message(ProductState.price)
async def product_price(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit(): await message.answer("فقط عدد وارد کنید."); return
    await state.update_data(price=int(message.text)); await state.set_state(ProductState.stock); await message.answer("موجودی اولیه:")

@router.message(ProductState.stock)
async def product_stock(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit(): await message.answer("فقط عدد وارد کنید."); return
    await state.update_data(stock=int(message.text)); await state.set_state(ProductState.photo); await message.answer("عکس محصول را بفرستید یا /skip بزنید:")

@router.message(ProductState.photo)
async def product_photo(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data(); photo_id = message.photo[-1].file_id if message.photo else None
    await db.execute("INSERT INTO products(name,description,price,stock,photo_id) VALUES(?,?,?,?,?)", (data["name"], data["description"], data["price"], data["stock"], photo_id))
    await state.clear(); await message.answer("محصول با موفقیت اضافه شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data == "admin_products")
async def admin_products(call: CallbackQuery, db: Database) -> None:
    rows = await db.fetchall("SELECT * FROM products ORDER BY id DESC")
    lines = ["📦 مدیریت محصولات"]
    items = []
    for row in rows:
        status = "✅ فعال" if row["is_active"] else "⛔ غیرفعال"
        lines.append(f"{row['id']}. {row['name']} | {row['price']:,} تومان | موجودی {row['stock']} | {status}")
        items.extend([
            button(f"✏️ ویرایش {row['name']}", f"edit_product:{row['id']}", ButtonStyle.SUCCESS),
            button(f"{'⛔ غیرفعال' if row['is_active'] else '✅ فعال'} {row['name']}", f"toggle_product:{row['id']}", ButtonStyle.PRIMARY),
            button(f"🗑 حذف کامل {row['name']}", f"delete_product:{row['id']}", ButtonStyle.DANGER),
        ])
    items.append(button("↩️ مدیریت", "admin"))
    await safe_edit(call, "\n".join(lines), grid(items, 3))

@router.callback_query(F.data.startswith("delete_product:"))
async def delete_product(call: CallbackQuery, db: Database) -> None:
    await db.delete_product(int(call.data.split(":")[1])); await call.answer("محصول کامل حذف شد ✅"); await admin_products(call, db)


@router.callback_query(F.data.startswith("toggle_product:"))
async def toggle_product(call: CallbackQuery, db: Database) -> None:
    product_id = int(call.data.split(":")[1])
    await db.execute("UPDATE products SET is_active=CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (product_id,))
    await call.answer("وضعیت محصول تغییر کرد ✅")
    await admin_products(call, db)


@router.callback_query(F.data.startswith("edit_product:"))
async def edit_product_start(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    product_id = int(call.data.split(":")[1])
    row = await db.fetchone("SELECT * FROM products WHERE id=?", (product_id,))
    if not row:
        await call.answer("محصول پیدا نشد", show_alert=True)
        return
    await state.update_data(product_id=product_id, photo_id=row["photo_id"])
    await state.set_state(EditProductState.name)
    await call.answer()
    await safe_edit(call, f"نام جدید محصول را بفرستید:\nنام فعلی: {row['name']}", back_menu("admin_products"))


@router.message(EditProductState.name)
async def edit_product_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text); await state.set_state(EditProductState.description); await message.answer("توضیحات جدید محصول:")


@router.message(EditProductState.description)
async def edit_product_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text); await state.set_state(EditProductState.price); await message.answer("قیمت جدید به تومان:")


@router.message(EditProductState.price)
async def edit_product_price(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await message.answer("قیمت باید فقط عدد باشد."); return
    await state.update_data(price=int(message.text)); await state.set_state(EditProductState.stock); await message.answer("موجودی جدید:")


@router.message(EditProductState.stock)
async def edit_product_stock(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await message.answer("موجودی باید فقط عدد باشد."); return
    await state.update_data(stock=int(message.text)); await state.set_state(EditProductState.photo); await message.answer("عکس جدید را بفرستید یا /skip بزنید تا عکس قبلی بماند:")


@router.message(EditProductState.photo)
async def edit_product_photo(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    photo_id = message.photo[-1].file_id if message.photo else data.get("photo_id")
    await db.execute(
        "UPDATE products SET name=?, description=?, price=?, stock=?, photo_id=? WHERE id=?",
        (data["name"], data["description"], data["price"], data["stock"], photo_id, data["product_id"]),
    )
    await state.clear()
    await message.answer("اطلاعات محصول با موفقیت ویرایش شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data == "admin_cards")
async def cards(call: CallbackQuery, db: Database) -> None:
    rows = await db.fetchall("SELECT * FROM cards ORDER BY id DESC")
    lines = ["💳 مدیریت کارت‌های بانکی"]
    items = []
    for row in rows:
        status = "✅ فعال" if row["is_active"] else "⛔ غیرفعال"
        lines.append(f"{row['id']}. {row['title']} - {row['number']} | {status}")
        items.extend([
            button(f"✏️ ویرایش {row['title']}", f"edit_card:{row['id']}", ButtonStyle.SUCCESS),
            button(f"{'⛔ غیرفعال' if row['is_active'] else '✅ فعال'} {row['title']}", f"toggle_card:{row['id']}", ButtonStyle.PRIMARY),
            button(f"🗑 حذف کامل {row['title']}", f"delete_card:{row['id']}", ButtonStyle.DANGER),
        ])
    items += [button("➕ افزودن کارت", "add_card", ButtonStyle.SUCCESS), button("↩️ مدیریت", "admin")]
    await safe_edit(call, "\n".join(lines), grid(items, 3))

@router.callback_query(F.data == "add_card")
async def add_card_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CardState.title); await call.answer(); await safe_edit(call, "عنوان کارت (مثلاً بانک سامان):", back_menu("admin_cards"))

@router.message(CardState.title)
async def card_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text); await state.set_state(CardState.number); await message.answer("شماره کارت ۱۶ رقمی:")

@router.message(CardState.number)
async def card_number(message: Message, state: FSMContext) -> None:
    number = (message.text or "").replace(" ", "")
    if not number.isdigit() or len(number) != 16:
        await message.answer("شماره کارت باید دقیقاً ۱۶ رقم باشد.")
        return
    await state.update_data(number=number); await state.set_state(CardState.holder); await message.answer("نام صاحب کارت:")

@router.message(CardState.holder)
async def card_holder(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data(); await db.execute("INSERT INTO cards(title,number,holder) VALUES(?,?,?)", (data["title"], data["number"], message.text)); await state.clear(); await message.answer("کارت اضافه شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data.startswith("delete_card:"))
async def delete_card(call: CallbackQuery, db: Database) -> None:
    await db.execute("DELETE FROM cards WHERE id=?", (int(call.data.split(":")[1]),)); await call.answer("کارت کامل حذف شد ✅"); await cards(call, db)


@router.callback_query(F.data.startswith("toggle_card:"))
async def toggle_card(call: CallbackQuery, db: Database) -> None:
    card_id = int(call.data.split(":")[1])
    await db.execute("UPDATE cards SET is_active=CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (card_id,))
    await call.answer("وضعیت کارت تغییر کرد ✅")
    await cards(call, db)


@router.callback_query(F.data.startswith("edit_card:"))
async def edit_card_start(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    card_id = int(call.data.split(":")[1])
    row = await db.fetchone("SELECT * FROM cards WHERE id=?", (card_id,))
    if not row:
        await call.answer("کارت پیدا نشد", show_alert=True)
        return
    await state.update_data(card_id=card_id)
    await state.set_state(EditCardState.title)
    await call.answer()
    await safe_edit(call, f"عنوان جدید کارت را بفرستید:\nعنوان فعلی: {row['title']}", back_menu("admin_cards"))


@router.message(EditCardState.title)
async def edit_card_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text); await state.set_state(EditCardState.number); await message.answer("شماره کارت جدید:")


@router.message(EditCardState.number)
async def edit_card_number(message: Message, state: FSMContext) -> None:
    number = message.text.replace(" ", "")
    if not number.isdigit() or len(number) != 16:
        await message.answer("شماره کارت باید ۱۶ رقم باشد."); return
    await state.update_data(number=number); await state.set_state(EditCardState.holder); await message.answer("نام صاحب کارت جدید:")


@router.message(EditCardState.holder)
async def edit_card_holder(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    await db.execute("UPDATE cards SET title=?, number=?, holder=? WHERE id=?", (data["title"], data["number"], message.text, data["card_id"]))
    await state.clear()
    await message.answer("اطلاعات کارت با موفقیت ویرایش شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastState.message); await call.answer(); await safe_edit(call, "متن پیام همگانی را بفرستید:", back_menu("admin"))

@router.message(BroadcastState.message)
async def broadcast(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    users = await db.fetchall("SELECT id FROM users WHERE is_blocked=0")
    sent = 0
    for user in users:
        try: await bot.copy_message(user["id"], message.chat.id, message.message_id); sent += 1
        except Exception: pass
        await asyncio.sleep(0.03)
    await state.clear(); await message.answer(f"پیام برای {sent} کاربر ارسال شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data == "admin_backup")
async def backup(call: CallbackQuery, db: Database, settings: Settings) -> None:
    if not await is_admin(db, call.from_user.id, settings):
        await call.answer("دسترسی ندارید.", show_alert=True)
        return
    await call.answer()
    markup = grid([
        button("⬇️ دریافت بکاپ", "download_backup", ButtonStyle.SUCCESS),
        button("⬆️ بازگردانی بکاپ", "restore_backup", ButtonStyle.PRIMARY),
        button("↩️ مدیریت", "admin", ButtonStyle.DANGER),
    ], 1)
    await safe_edit(call, "💾 مدیریت دیتابیس\n\nعملیات مورد نظر را انتخاب کنید:", markup)


@router.callback_query(F.data == "download_backup")
async def download_backup(call: CallbackQuery, db: Database, settings: Settings) -> None:
    if not await is_admin(db, call.from_user.id, settings):
        await call.answer("دسترسی ندارید.", show_alert=True)
        return
    temporary = tempfile.NamedTemporaryFile(prefix=f"backup_{call.from_user.id}_", suffix=".sqlite3", delete=False)
    temporary.close()
    target = temporary.name
    await call.answer("در حال آماده‌سازی بکاپ...")
    await db_backup(call, settings, target)


@router.callback_query(F.data == "restore_backup")
async def restore_backup_start(call: CallbackQuery, state: FSMContext, db: Database, settings: Settings) -> None:
    if not await is_admin(db, call.from_user.id, settings):
        await call.answer("دسترسی ندارید.", show_alert=True)
        return
    await call.answer()
    await state.set_state(BackupState.waiting_file)
    await safe_edit(call, "فایل SQLite بکاپ را به‌صورت Document ارسال کنید:", back_menu("admin_backup"))


@router.message(BackupState.waiting_file, F.document)
async def restore_backup_file(message: Message, state: FSMContext, bot: Bot, db: Database, settings: Settings) -> None:
    if not await is_admin(db, message.from_user.id, settings):
        await state.clear()
        return
    if not message.document.file_name.lower().endswith((".sqlite3", ".db", ".sqlite")):
        await message.answer("فقط فایل SQLite با پسوند .sqlite3، .db یا .sqlite قابل بازگردانی است.")
        return
    target = Path(f"restore_{message.from_user.id}.sqlite3")
    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, destination=target)
    if not await db.is_valid_backup(str(target)):
        target.unlink(missing_ok=True)
        await state.clear()
        await message.answer("فایل بکاپ معتبر نیست.", reply_markup=admin_menu())
        return
    previous = Path(f"{settings.db_path}.before_restore")
    previous.unlink(missing_ok=True)
    Path(settings.db_path).replace(previous)
    target.replace(Path(settings.db_path))
    await state.clear()
    await message.answer("دیتابیس با موفقیت بازگردانی شد ✅", reply_markup=admin_menu())

async def db_backup(call: CallbackQuery, settings: Settings, target: str) -> None:
    try:
        db = Database(settings.db_path)
        await db.backup(target)
        await call.message.answer_document(FSInputFile(target), caption="💾 بکاپ دیتابیس آماده شد")
    except Exception:
        logger.exception("Could not create database backup")
        await call.message.answer("ساخت بکاپ انجام نشد. لاگ اجرای ربات را بررسی کنید.")
    finally:
        Path(target).unlink(missing_ok=True)

@router.callback_query(F.data == "admin_admins")
async def admins(call: CallbackQuery, db: Database) -> None:
    rows = await db.fetchall("SELECT * FROM admins ORDER BY user_id")
    text = "👥 مدیران\n" + ("\n".join(f"{r['user_id']} | {r['title']} | {r['permissions']}" for r in rows) or "مدیر دیگری ثبت نشده است.")
    items = [button(f"🗑 حذف {r['user_id']}", f"delete_admin:{r['user_id']}", ButtonStyle.DANGER) for r in rows]
    items += [button("➕ افزودن مدیر", "add_admin", ButtonStyle.SUCCESS), button("↩️ مدیریت", "admin")]
    await safe_edit(call, text, grid(items, 1))

@router.callback_query(F.data == "add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer(); await state.set_state(AdminState.user_id)
    await safe_edit(call, "شناسه عددی کاربر را بفرستید:", back_menu("admin_admins"))

@router.message(AdminState.user_id)
async def admin_user_id(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await message.answer("شناسه باید عددی باشد."); return
    await state.update_data(user_id=int(message.text)); await state.set_state(AdminState.permissions)
    await message.answer("مجوزها را با کاما بفرستید: products,orders,support,broadcast,settings")

@router.message(AdminState.permissions)
async def admin_permissions(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    await db.execute("INSERT INTO admins(user_id,permissions) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET permissions=excluded.permissions", (data["user_id"], message.text.replace(" ", "")))
    await state.clear(); await message.answer("مدیر با موفقیت ثبت شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data.startswith("delete_admin:"))
async def delete_admin(call: CallbackQuery, db: Database) -> None:
    await db.execute("DELETE FROM admins WHERE user_id=?", (int(call.data.split(":")[1]),)); await call.answer("مدیر حذف شد"); await admins(call, db)

@router.callback_query(F.data == "admin_block")
async def blocked_users(call: CallbackQuery, db: Database) -> None:
    rows = await db.fetchall("SELECT id,full_name,is_blocked FROM users ORDER BY joined_at DESC LIMIT 30")
    text = "🚫 مدیریت کاربران\n" + ("\n".join(f"{r['id']} | {r['full_name']} | {'مسدود' if r['is_blocked'] else 'فعال'}" for r in rows) or "کاربری ثبت نشده است.")
    items = [button(f"{'✅ رفع' if r['is_blocked'] else '🚫 مسدود'} {r['id']}", f"toggle_block:{r['id']}", ButtonStyle.SUCCESS if r['is_blocked'] else ButtonStyle.DANGER) for r in rows]
    items.append(button("↩️ مدیریت", "admin")); await safe_edit(call, text, grid(items, 1))

@router.callback_query(F.data.startswith("toggle_block:"))
async def toggle_block(call: CallbackQuery, db: Database) -> None:
    user_id = int(call.data.split(":")[1])
    await db.execute("UPDATE users SET is_blocked=CASE is_blocked WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (user_id,)); await call.answer("وضعیت کاربر تغییر کرد"); await blocked_users(call, db)

@router.callback_query(F.data == "admin_channels")
async def channels(call: CallbackQuery, db: Database) -> None:
    rows = await db.fetchall("SELECT * FROM channels WHERE is_active=1")
    text = "📢 عضویت اجباری\n" + ("\n".join(f"{r['title']} | {r['chat_id']}" for r in rows) or "کانالی ثبت نشده است.")
    items = [button(f"🗑 حذف {r['title']}", f"delete_channel:{r['id']}", ButtonStyle.DANGER) for r in rows]
    items += [button("➕ افزودن کانال", "add_channel", ButtonStyle.SUCCESS), button("↩️ مدیریت", "admin")]
    await safe_edit(call, text, grid(items, 1))

@router.callback_query(F.data == "add_channel")
async def add_channel_start(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer(); await state.set_state(ChannelState.chat_id); await safe_edit(call, "شناسه کانال یا گروه را بفرستید (مثل -100...):", back_menu("admin_channels"))

@router.message(ChannelState.chat_id)
async def channel_chat_id(message: Message, state: FSMContext) -> None:
    await state.update_data(chat_id=message.text); await state.set_state(ChannelState.title); await message.answer("نام نمایشی کانال:")

@router.message(ChannelState.title)
async def channel_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text); await state.set_state(ChannelState.link); await message.answer("لینک عضویت کانال:")

@router.message(ChannelState.link)
async def channel_link(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data(); await db.execute("INSERT INTO channels(chat_id,title,invite_link) VALUES(?,?,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,invite_link=excluded.invite_link,is_active=1", (data["chat_id"], data["title"], message.text)); await state.clear(); await message.answer("کانال ثبت شد ✅", reply_markup=admin_menu())

@router.callback_query(F.data.startswith("delete_channel:"))
async def delete_channel(call: CallbackQuery, db: Database) -> None:
    await db.execute("UPDATE channels SET is_active=0 WHERE id=?", (int(call.data.split(":")[1]),)); await call.answer("کانال حذف شد"); await channels(call, db)
