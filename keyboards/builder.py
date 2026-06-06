from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def items_kb(items) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"{item.name} | {item.price} ₽", callback_data=f"item_{item.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()
