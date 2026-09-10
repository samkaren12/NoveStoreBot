from aiogram.enums import ButtonStyle
from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def button(text: str, callback_data: str, style: ButtonStyle = ButtonStyle.PRIMARY) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)


def copy_button(text: str, value: str, style: ButtonStyle = ButtonStyle.PRIMARY) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, copy_text=CopyTextButton(text=value), style=style)


MENU_DEFAULTS = {
    "products": {"label": "🛍 محصولات", "color": ButtonStyle.DANGER.value, "order": 1},
    "cart": {"label": "🧺 سبد خرید", "color": ButtonStyle.SUCCESS.value, "order": 2},
    "profile": {"label": "👤 مشخصات من", "color": ButtonStyle.PRIMARY.value, "order": 3},
    "support": {"label": "💬 پشتیبانی", "color": ButtonStyle.DANGER.value, "order": 4},
    "help": {"label": "📚 راهنما", "color": ButtonStyle.SUCCESS.value, "order": 5},
    "rules": {"label": "📜 قوانین", "color": ButtonStyle.PRIMARY.value, "order": 6},
}


def grid(items: list[InlineKeyboardButton], width: int = 3, cycle_colors: bool = True) -> InlineKeyboardMarkup:
    if cycle_colors:
        styles = (ButtonStyle.DANGER, ButtonStyle.SUCCESS, ButtonStyle.PRIMARY)
        items = [item.model_copy(update={"style": styles[index % len(styles)]}) for index, item in enumerate(items)]
    return InlineKeyboardMarkup(
        inline_keyboard=[items[index:index + width] for index in range(0, len(items), width)]
    )


def main_menu(is_admin: bool = False, mode: str = "keyboard", config: dict | None = None) -> ReplyKeyboardMarkup | InlineKeyboardMarkup:
    config = config or MENU_DEFAULTS
    ordered = sorted(config.items(), key=lambda item: item[1]["order"])
    if mode == "glass":
        items = [button(item["label"], key, ButtonStyle(item["color"])) for key, item in ordered]
        if is_admin:
            items.append(button("⚙️ مدیریت", "admin"))
        return grid(items, cycle_colors=False)
    # Reply keyboards support KeyboardButton, but Telegram does not expose button colors for them.
    rows = []
    labels = [KeyboardButton(text=item["label"]) for _, item in ordered]
    rows.extend(labels[index:index + 3] for index in range(0, len(labels), 3))
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ مدیریت"), KeyboardButton(text="🏠 منوی اصلی")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def back_menu(target: str = "home") -> InlineKeyboardMarkup:
    return grid([button("↩️ بازگشت", target, ButtonStyle.PRIMARY)], 1)


def admin_menu() -> InlineKeyboardMarkup:
    return grid([
        button("➕ محصول جدید", "admin_add_product", ButtonStyle.SUCCESS),
        button("📦 مدیریت محصولات", "admin_products", ButtonStyle.PRIMARY),
        button("📣 پیام همگانی", "admin_broadcast", ButtonStyle.DANGER),
        button("💳 کارت‌های بانکی", "admin_cards", ButtonStyle.PRIMARY),
        button("👥 مدیران", "admin_admins", ButtonStyle.SUCCESS),
        button("🚫 کاربران مسدود", "admin_block", ButtonStyle.DANGER),
        button("📢 عضویت اجباری", "admin_channels", ButtonStyle.PRIMARY),
        button("💾 بکاپ / بازگردانی", "admin_backup", ButtonStyle.SUCCESS),
        button("🎛 تغییر حالت دکمه‌ها", "toggle_ui_mode", ButtonStyle.PRIMARY),
        button("🖌 شخصی‌سازی منوی اصلی", "customize_menu", ButtonStyle.SUCCESS),
        button("🏷 نام فروشگاه", "shop_name", ButtonStyle.SUCCESS),
        button("🌐 پنل وب", "web_panel", ButtonStyle.PRIMARY),
        button("🏠 منوی اصلی", "home", ButtonStyle.PRIMARY),
    ])
