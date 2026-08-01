from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import split_list


# -------------------- USER --------------------

def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🛍 Каталог", callback_data="catalog")],
        [
            InlineKeyboardButton(text="💼 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit")
        ],
        [
            InlineKeyboardButton(text="🎁 Промокод", callback_data="promo"),
            InlineKeyboardButton(text="🤖 Поддержка ИИ", callback_data="ai_support")
        ],
        [InlineKeyboardButton(text="📢 Канал", url="https://t.me/sweg_shop_channel")]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def categories_keyboard(categories: list, back_callback: str = "main_menu") -> InlineKeyboardMarkup:
    kb = []
    for cat in categories:
        name = cat.get("name", "Без названия")
        emoji = cat.get("emoji", "🔹")
        cid = cat.get("id")
        kb.append([InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"cat_{cid}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def products_keyboard(products: list, back_callback: str = "catalog") -> InlineKeyboardMarkup:
    kb = []
    rows = split_list(products, 2)
    for row in rows:
        kb.append([
            InlineKeyboardButton(
                text=f"{p.get('name', 'Товар')} — {p.get('price', 0)} ₽",
                callback_data=f"product_{p.get('id')}"
            )
            for p in row
        ])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def product_detail_keyboard(product_id: int, has_keys: bool, back_callback: str = "catalog") -> InlineKeyboardMarkup:
    kb = []
    if has_keys:
        kb.append([InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_{product_id}")])
    else:
        kb.append([InlineKeyboardButton(text="⛔ Нет в наличии", callback_data="empty")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def deposit_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="💳 Platega", callback_data="deposit_platega"),
            InlineKeyboardButton(text="₿ CryptoBot", callback_data="deposit_crypto")
        ],
        [
            InlineKeyboardButton(text="100 ₽", callback_data="dep_amount_100"),
            InlineKeyboardButton(text="300 ₽", callback_data="dep_amount_300"),
            InlineKeyboardButton(text="500 ₽", callback_data="dep_amount_500")
        ],
        [
            InlineKeyboardButton(text="1000 ₽", callback_data="dep_amount_1000"),
            InlineKeyboardButton(text="2500 ₽", callback_data="dep_amount_2500")
        ],
        [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="dep_custom")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_keyboard(back_callback: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
    ])


# -------------------- ADMIN --------------------

def admin_main_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📦 Товары", callback_data="admin_products")],
        [InlineKeyboardButton(text="📁 Категории", callback_data="admin_categories")],
        [InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin_promos")],
        [InlineKeyboardButton(text="🤖 ИИ-настройки", callback_data="admin_ai_settings")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_products_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="📋 Список товаров", callback_data="admin_list_products")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_categories_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="📋 Список категорий", callback_data="admin_list_categories")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_promos_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_add_promo")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_settings_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📝 Текст ручной оплаты", callback_data="admin_custom_text")],
        [InlineKeyboardButton(text="💸 Комиссия CryptoBot", callback_data="admin_crypto_fee")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_ai_settings_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📝 Изменить промпт", callback_data="admin_ai_prompt")],
        [InlineKeyboardButton(text="🔁 Вкл/Выкл ИИ", callback_data="admin_ai_toggle")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_ai_stats")],
        [InlineKeyboardButton(text="🗑 Очистить историю", callback_data="admin_ai_clear")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def product_admin_keyboard(product_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_edit_product_{product_id}")],
        [InlineKeyboardButton(text="🔑 Добавить ключи", callback_data=f"admin_add_keys_{product_id}")],
        [InlineKeyboardButton(text="📋 Показать ключи", callback_data=f"admin_view_keys_{product_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_delete_product_{product_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_list_products")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def category_admin_keyboard(category_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_edit_cat_{category_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_delete_cat_{category_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_list_categories")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def promo_admin_keyboard(promo_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_delete_promo_{promo_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_list_promos")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def confirm_broadcast_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def edit_product_field_keyboard(product_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🏷 Название", callback_data=f"edit_field_{product_id}_name")],
        [InlineKeyboardButton(text="📝 Описание", callback_data=f"edit_field_{product_id}_description")],
        [InlineKeyboardButton(text="💰 Цена", callback_data=f"edit_field_{product_id}_price")],
        [InlineKeyboardButton(text="📁 Категория", callback_data=f"edit_field_{product_id}_category_id")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_product_{product_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
