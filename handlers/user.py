from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from database.requests import add_user, get_user, get_all_items
from keyboards.inline import main_menu_kb, profile_kb
from keyboards.builder import items_kb

user_router = Router()

@user_router.message(CommandStart())
async def cmd_start(message: Message):
    await add_user(message.from_user.id)
    text = (
        "<b>👋 Добро пожаловать в магазин!</b>\n\n"
        "Для покупки товаров используйте кнопки ниже ⬇️"
    )
    await message.answer(text, reply_markup=main_menu_kb())

@user_router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    text = (
        "<b>👋 Добро пожаловать в магазин!</b>\n\n"
        "Для покупки товаров используйте кнопки ниже ⬇️"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()

@user_router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    text = (
        "<b>👤 Профиль</b>\n\n"
        f"<blockquote>"
        f"<b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"<b>Ваш баланс:</b> <code>{user.balance} ₽</code>"
        f"</blockquote>"
    )
    await callback.message.edit_text(text, reply_markup=profile_kb())
    await callback.answer()

@user_router.callback_query(F.data == "deposit")
async def process_deposit(callback: CallbackQuery):
    await callback.answer("Метод пополнения в разработке (API заказчика)", show_alert=True)

@user_router.callback_query(F.data == "shop")
async def show_shop(callback: CallbackQuery):
    items = await get_all_items()
    if not items:
        await callback.message.edit_text(
            "<b>🛍 Магазин пуст</b>\n\n"
            "Товары скоро появятся!",
            reply_markup=main_menu_kb()
        )
        return

    text = "<b>🛍 Доступные товары:</b>\n\nВыберите нужный товар из списка ниже:"
    await callback.message.edit_text(text, reply_markup=items_kb(items))
    await callback.answer()

@user_router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):
    text = (
        "<b>📢 Служба поддержки</b>\n\n"
        "Если у вас возникли проблемы, обратитесь к администратору."
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()
    
