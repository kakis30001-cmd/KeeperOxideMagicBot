import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import (
    get_all_categories,
    get_category_by_id,
    create_category,
    update_category,
    delete_category,
    get_all_products,
    get_product_by_id,
    add_product,
    update_product,
    delete_product,
    add_keys_to_product,
    get_keys_by_product,
    delete_key,
    count_keys,
    get_all_promocodes,
    create_promocode,
    delete_promocode,
    get_stats,
    get_all_users,
    get_setting,
    update_setting,
    set_crypto_fee,
    get_ai_setting,
    update_ai_setting,
    clear_ai_chat_history,
)
from keyboards import (
    admin_main_keyboard,
    admin_products_menu_keyboard,
    admin_categories_menu_keyboard,
    admin_promos_menu_keyboard,
    admin_ai_settings_keyboard,
    admin_settings_menu_keyboard,
    categories_keyboard,
    product_admin_keyboard,
    category_admin_keyboard,
    promo_admin_keyboard,
    confirm_broadcast_keyboard,
    edit_product_field_keyboard,
    back_keyboard,
    cancel_keyboard,
)
from utils import is_admin, escape_html, format_price
from states import (
    AdminCategoryStates,
    AdminProductStates,
    AdminPromocodeStates,
    AdminAIPromptStates,
    AdminBroadcastState,
    AdminSettingsStates,
)

router = Router()


def admin_only(func):
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ Доступ запрещен", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper


# ========== Главная админка ==========

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "⚙️ <b>Админ-панель</b>",
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_panel")
@admin_only
async def admin_panel(callback: CallbackQuery):
    await callback.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=admin_main_keyboard(), parse_mode="HTML")
    await callback.answer()


# ========== Товары ==========

@router.callback_query(F.data == "admin_products")
@admin_only
async def admin_products(callback: CallbackQuery):
    await callback.message.edit_text(
        "📦 <b>Управление товарами</b>",
        reply_markup=admin_products_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_list_products")
@admin_only
async def admin_list_products(callback: CallbackQuery):
    products = await get_all_products()
    if not products:
        await callback.answer("Товаров нет", show_alert=True)
        return

    text = "📦 <b>Список товаров</b>\n\n"
    for p in products:
        counts = await count_keys(p["id"])
        text += (
            f"• <b>{escape_html(p['name'])}</b> — {format_price(p['price'])}\n"
            f"  В наличии: {counts['left']} / {counts['total']}\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=admin_products_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_product")
@admin_only
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminProductStates.waiting_name)
    await callback.message.edit_text(
        "➕ <b>Добавление товара</b>\n\nВведите название:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminProductStates.waiting_description)
    await message.answer("📝 Введите описание товара:", reply_markup=cancel_keyboard())


@router.message(AdminProductStates.waiting_description)
async def product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminProductStates.waiting_price)
    await message.answer("💰 Введите цену (число):", reply_markup=cancel_keyboard())


@router.message(AdminProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите число:", reply_markup=cancel_keyboard())
        return
    await state.update_data(price=int(message.text))

    categories = await get_all_categories()
    if not categories:
        await state.update_data(category_id=None)
        await state.set_state(AdminProductStates.waiting_photo)
        await message.answer(
            "📁 Категорий нет. Отправьте фото товара или напишите 'пропустить':",
            reply_markup=cancel_keyboard()
        )
        return

    await state.set_state(AdminProductStates.waiting_category)
    await message.answer(
        "📁 Выберите категорию:",
        reply_markup=categories_keyboard(categories, back_callback="admin_products")
    )


@router.callback_query(AdminProductStates.waiting_category, F.data.startswith("cat_"))
async def product_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(AdminProductStates.waiting_photo)
    await callback.message.edit_text(
        "📷 Отправьте фото товара или напишите 'пропустить':",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminProductStates.waiting_photo)
async def product_photo(message: Message, state: FSMContext):
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.text.strip().lower() != "пропустить":
        await message.answer("❌ Отправьте фото или напишите 'пропустить':", reply_markup=cancel_keyboard())
        return

    await state.update_data(photo_id=photo_id)
    await state.set_state(AdminProductStates.waiting_keys)

    data = await state.get_data()
    product_id = await add_product(
        name=data["name"],
        price=data["price"],
        category_id=data.get("category_id"),
        description=data["description"],
        photo_id=photo_id
    )
    await state.update_data(product_id=product_id)

    await message.answer(
        f"✅ Товар <b>{escape_html(data['name'])}</b> создан!\n\n"
        f"Теперь отправьте ключи (по одному на строку):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AdminProductStates.waiting_keys)
async def product_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    if not keys:
        await message.answer("❌ Отправьте хотя бы один ключ:", reply_markup=cancel_keyboard())
        return

    await add_keys_to_product(product_id, keys)
    counts = await count_keys(product_id)
    await message.answer(
        f"✅ Добавлено <b>{len(keys)}</b> ключей.\n"
        f"Всего у товара: {counts['total']}",
        reply_markup=back_keyboard("admin_products"),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("admin_product_"))
@admin_only
async def admin_product_detail(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    product = await get_product_by_id(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    counts = await count_keys(product_id)
    text = (
        f"📦 <b>{escape_html(product['name'])}</b>\n\n"
        f"📝 {escape_html(product['description']) or '—'}\n"
        f"💰 {format_price(product['price'])}\n"
        f"📦 Ключей: {counts['left']} / {counts['total']}"
    )
    await callback.message.edit_text(text, reply_markup=product_admin_keyboard(product_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_product_"))
@admin_only
async def admin_edit_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[3])
    await callback.message.edit_text(
        "✏️ Выберите поле для редактирования:",
        reply_markup=edit_product_field_keyboard(product_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field_"))
@admin_only
async def edit_field_select(callback: CallbackQuery, state: FSMContext):
    _, _, product_id, field = callback.data.split("_")
    product_id = int(product_id)
    await state.update_data(product_id=product_id, field=field)
    await state.set_state(AdminProductStates.edit_field)

    prompts = {
        "name": "Введите новое название:",
        "description": "Введите новое описание:",
        "price": "Введите новую цену:",
        "category": "Выберите новую категорию:",
    }
    if field == "category_id":
        categories = await get_all_categories()
        await callback.message.edit_text(
            "📁 Выберите категорию:",
            reply_markup=categories_keyboard(categories, back_callback=f"admin_product_{product_id}"),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(prompts.get(field, "Введите новое значение:"), reply_markup=cancel_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminProductStates.edit_field)
async def edit_field_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["field"]
    product_id = data["product_id"]

    if field == "price" and not message.text.isdigit():
        await message.answer("❌ Цена должна быть числом:", reply_markup=cancel_keyboard())
        return

    value = int(message.text) if field == "price" else message.text.strip()
    await update_product(product_id, **{field: value})
    await message.answer("✅ Изменения сохранены", reply_markup=back_keyboard("admin_products"))
    await state.clear()


@router.callback_query(AdminProductStates.edit_field, F.data.startswith("cat_"))
async def edit_field_category(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category_id = int(callback.data.split("_")[1])
    await update_product(data["product_id"], category_id=category_id)
    await callback.message.edit_text("✅ Категория обновлена", reply_markup=back_keyboard("admin_products"), parse_mode="HTML")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("admin_add_keys_"))
@admin_only
async def admin_add_keys_start(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[3])
    await state.update_data(product_id=product_id)
    await state.set_state(AdminProductStates.waiting_keys)
    await callback.message.edit_text(
        "🔑 Отправьте ключи (по одному на строку):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view_keys_"))
@admin_only
async def admin_view_keys(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[3])
    keys = await get_keys_by_product(product_id)
    text = f"🔑 <b>Ключи товара</b> ({len(keys)} шт.)\n\n"
    for k in keys[:50]:
        status = "✅" if not k["used"] else "❌"
        text += f"{status} <code>{escape_html(k['key_value'])}</code>\n"
    if len(keys) > 50:
        text += f"\n... и ещё {len(keys) - 50}"

    await callback.message.edit_text(
        text,
        reply_markup=product_admin_keyboard(product_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_product_"))
@admin_only
async def admin_delete_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[3])
    await delete_product(product_id)
    await callback.message.edit_text("🗑 Товар удалён", reply_markup=back_keyboard("admin_products"), parse_mode="HTML")
    await callback.answer()


# ========== Категории ==========

@router.callback_query(F.data == "admin_categories")
@admin_only
async def admin_categories(callback: CallbackQuery):
    await callback.message.edit_text(
        "📁 <b>Управление категориями</b>",
        reply_markup=admin_categories_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_category")
@admin_only
async def admin_add_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminCategoryStates.waiting_name)
    await callback.message.edit_text(
        "➕ <b>Новая категория</b>\n\nВведите название:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCategoryStates.waiting_name)
async def category_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminCategoryStates.waiting_emoji)
    await message.answer("🔹 Введите эмодзи для категории:", reply_markup=cancel_keyboard())


@router.message(AdminCategoryStates.waiting_emoji)
async def category_emoji(message: Message, state: FSMContext):
    emoji = message.text.strip()[:2]
    data = await state.get_data()
    category_id = await create_category(data["name"], emoji)
    await message.answer(
        f"✅ Категория <b>{escape_html(data['name'])}</b> создана!",
        reply_markup=back_keyboard("admin_categories"),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "admin_list_categories")
@admin_only
async def admin_list_categories(callback: CallbackQuery):
    categories = await get_all_categories()
    if not categories:
        await callback.answer("Категорий нет", show_alert=True)
        return

    await callback.message.edit_text(
        "📁 <b>Категории</b>",
        reply_markup=categories_keyboard(categories, back_callback="admin_categories"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_cat_"))
@admin_only
async def admin_edit_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[3])
    await state.update_data(category_id=category_id)
    await state.set_state(AdminCategoryStates.edit_name)
    await callback.message.edit_text("✏️ Введите новое название:", reply_markup=cancel_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminCategoryStates.edit_name)
async def category_edit_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminCategoryStates.edit_emoji)
    await message.answer("🔹 Введите новое эмодзи:", reply_markup=cancel_keyboard())


@router.message(AdminCategoryStates.edit_emoji)
async def category_edit_emoji(message: Message, state: FSMContext):
    emoji = message.text.strip()[:2]
    data = await state.get_data()
    await update_category(data["category_id"], data["name"], emoji)
    await message.answer("✅ Категория обновлена", reply_markup=back_keyboard("admin_categories"))
    await state.clear()


@router.callback_query(F.data.startswith("admin_delete_cat_"))
@admin_only
async def admin_delete_category(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[3])
    await delete_category(category_id)
    await callback.message.edit_text("🗑 Категория удалена", reply_markup=back_keyboard("admin_categories"), parse_mode="HTML")
    await callback.answer()


# ========== Промокоды ==========

@router.callback_query(F.data == "admin_promos")
@admin_only
async def admin_promos(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>Промокоды</b>",
        reply_markup=admin_promos_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_promo")
@admin_only
async def admin_add_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminPromocodeStates.waiting_code)
    await callback.message.edit_text("🎁 Введите код промокода:", reply_markup=cancel_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminPromocodeStates.waiting_code)
async def promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await state.set_state(AdminPromocodeStates.waiting_type)
    await message.answer(
        "Выберите тип скидки:\n<b>percent</b> — процент\n<b>fixed</b> — фиксированная сумма",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AdminPromocodeStates.waiting_type)
async def promo_type(message: Message, state: FSMContext):
    value = message.text.strip().lower()
    if value not in ("percent", "fixed"):
        await message.answer("❌ Введите percent или fixed:", reply_markup=cancel_keyboard())
        return
    await state.update_data(discount_type=value)
    await state.set_state(AdminPromocodeStates.waiting_value)
    await message.answer("Введите размер скидки (число):", reply_markup=cancel_keyboard())


@router.message(AdminPromocodeStates.waiting_value)
async def promo_value(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите число:", reply_markup=cancel_keyboard())
        return
    await state.update_data(discount_value=int(message.text))
    await state.set_state(AdminPromocodeStates.waiting_uses)
    await message.answer("Введите максимальное количество использований:", reply_markup=cancel_keyboard())


@router.message(AdminPromocodeStates.waiting_uses)
async def promo_uses(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите число:", reply_markup=cancel_keyboard())
        return

    data = await state.get_data()
    await create_promocode(
        data["code"],
        data["discount_type"],
        data["discount_value"],
        int(message.text)
    )
    await message.answer(
        f"✅ Промокод <b>{escape_html(data['code'])}</b> создан!",
        reply_markup=back_keyboard("admin_promos"),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "admin_list_promos")
@admin_only
async def admin_list_promos(callback: CallbackQuery):
    promos = await get_all_promocodes()
    if not promos:
        await callback.answer("Промокодов нет", show_alert=True)
        return

    text = "🎁 <b>Промокоды</b>\n\n"
    for p in promos:
        dtype = "%" if p["discount_type"] == "percent" else "₽"
        active = "🟢" if p["is_active"] else "🔴"
        text += f"{active} <code>{escape_html(p['code'])}</code> — {p['discount_value']}{dtype} ({p['used_count']}/{p['max_uses']})\n"

    await callback.message.edit_text(text, reply_markup=admin_promos_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_promo_"))
@admin_only
async def admin_delete_promo(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[3])
    await delete_promocode(promo_id)
    await callback.message.edit_text("🗑 Промокод удалён", reply_markup=back_keyboard("admin_promos"), parse_mode="HTML")
    await callback.answer()


# ========== ИИ-настройки ==========

@router.callback_query(F.data == "admin_ai_settings")
@admin_only
async def admin_ai_settings(callback: CallbackQuery):
    ai_enabled = await get_ai_setting("ai_enabled")
    status = "🟢 Включен" if ai_enabled == "true" else "🔴 Выключен"
    model = await get_ai_setting("ai_model") or "—"
    prompt = await get_ai_setting("system_prompt") or ""

    text = (
        f"🤖 <b>Настройки ИИ</b>\n\n"
        f"Статус: {status}\n"
        f"Модель: <code>{escape_html(model)}</code>\n\n"
        f"📝 Промпт:\n<code>{escape_html(prompt[:200])}...</code>"
    )
    await callback.message.edit_text(text, reply_markup=admin_ai_settings_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_ai_prompt")
@admin_only
async def admin_ai_prompt(callback: CallbackQuery, state: FSMContext):
    current = await get_ai_setting("system_prompt")
    await state.set_state(AdminAIPromptStates.waiting_prompt)
    await callback.message.edit_text(
        f"📝 <b>Изменение промпта</b>\n\nТекущий:\n<code>{escape_html(current)}</code>\n\nВведите новый:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminAIPromptStates.waiting_prompt)
async def process_ai_prompt(message: Message, state: FSMContext):
    await update_ai_setting("system_prompt", message.text.strip())
    await message.answer("✅ Промпт обновлён", reply_markup=back_keyboard("admin_ai_settings"))
    await state.clear()


@router.callback_query(F.data == "admin_ai_toggle")
@admin_only
async def admin_ai_toggle(callback: CallbackQuery):
    current = await get_ai_setting("ai_enabled")
    new_value = "false" if current == "true" else "true"
    await update_ai_setting("ai_enabled", new_value)
    await callback.answer(f"ИИ {'выключен' if new_value == 'false' else 'включен'}")
    await admin_ai_settings(callback)


@router.callback_query(F.data == "admin_ai_stats")
@admin_only
async def admin_ai_stats(callback: CallbackQuery):
    # Реализовано в основном main.py через прямой доступ к pool
    from database import pool
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM ai_chat_history")
        unique = await conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM ai_chat_history")
        last_24h = await conn.fetchval("SELECT COUNT(*) FROM ai_chat_history WHERE created_at > NOW() - INTERVAL '24 hours'")

    await callback.message.edit_text(
        f"🤖 <b>Статистика ИИ</b>\n\n"
        f"📊 Всего сообщений: <code>{total}</code>\n"
        f"👥 Уникальных пользователей: <code>{unique}</code>\n"
        f"📈 За 24 часа: <code>{last_24h}</code>",
        reply_markup=back_keyboard("admin_ai_settings"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_ai_clear")
@admin_only
async def admin_ai_clear(callback: CallbackQuery):
    # Очистка всей истории — возможно, лучше спросить подтверждение
    from database import pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM ai_chat_history")
    await callback.answer("🗑 История ИИ очищена", show_alert=True)


# ========== Статистика ==========

@router.callback_query(F.data == "admin_stats")
@admin_only
async def admin_stats(callback: CallbackQuery):
    stats = await get_stats()
    text = (
        f"📊 <b>Статистика магазина</b>\n\n"
        f"👤 Пользователей: <code>{stats['users']}</code>\n"
        f"📦 Товаров: <code>{stats['products_count']}</code>\n"
        f"📁 Категорий: <code>{stats['categories_count']}</code>\n"
        f"🛒 Продаж на сумму: <code>{format_price(stats['total_sales'])}</code>\n"
        f"🔑 Ключей продано: <code>{stats['keys_sold']}</code>\n"
        f"🔑 Ключей в наличии: <code>{stats['keys_left']}</code>"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard("admin_panel"), parse_mode="HTML")
    await callback.answer()


# ========== Рассылка ==========

@router.callback_query(F.data == "admin_broadcast")
@admin_only
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminBroadcastState.waiting_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nОтправьте сообщение для рассылки:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminBroadcastState.waiting_message)
async def broadcast_message(message: Message, state: FSMContext):
    await state.update_data(text=message.html_text or message.text, has_media=False)
    await state.set_state(AdminBroadcastState.waiting_confirm)
    await message.answer(
        "📨 Предпросмотр сообщения:\n\n" + (message.html_text or message.text),
        reply_markup=confirm_broadcast_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast_confirm")
@admin_only
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data.get("text", "")
    users = await get_all_users()

    sent = 0
    failed = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await callback.message.edit_text(
        f"✅ Рассылка завершена\n\nДоставлено: <code>{sent}</code>\nНе доставлено: <code>{failed}</code>",
        reply_markup=back_keyboard("admin_panel"),
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


# ========== Настройки ==========

@router.callback_query(F.data == "admin_settings")
@admin_only
async def admin_settings(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>",
        reply_markup=admin_settings_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_custom_text")
@admin_only
async def admin_custom_text(callback: CallbackQuery, state: FSMContext):
    current = await get_setting("custom_text")
    await state.set_state(AdminSettingsStates.waiting_custom_text)
    await callback.message.edit_text(
        f"📝 <b>Текст ручной оплаты</b>\n\nТекущий:\n<code>{escape_html(current)}</code>\n\nВведите новый:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_custom_text)
async def process_custom_text(message: Message, state: FSMContext):
    await update_setting("custom_text", message.text.strip())
    await message.answer("✅ Текст обновлён", reply_markup=back_keyboard("admin_settings"))
    await state.clear()


@router.callback_query(F.data == "admin_crypto_fee")
@admin_only
async def admin_crypto_fee(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettingsStates.waiting_crypto_fee)
    await callback.message.edit_text(
        "💸 Введите комиссию CryptoBot (в процентах, например 5):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_crypto_fee)
async def process_crypto_fee(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите число:", reply_markup=cancel_keyboard())
        return
    await set_crypto_fee(int(message.text))
    await message.answer("✅ Комиссия обновлена", reply_markup=back_keyboard("admin_settings"))
    await state.clear()
