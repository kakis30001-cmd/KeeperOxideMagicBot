from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏪 Магазин", callback_data="shop")],
            [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton(text="📢 Поддержка", callback_data="support")],
            [InlineKeyboardButton(text="ℹ️ Правила", callback_data="rules")]
        ]
    )

def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit")],
            [InlineKeyboardButton(text="🛍 История заказов", callback_data="history")],
            [InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")]
        ]
    )
