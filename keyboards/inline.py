from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Словник іконок для відображення у звітах (Твердо закодований для безпеки)
category_icons_map = {
    "Продукти": "🍔",
    "Здоровʼя": "💊",
    "Спорт": "🏋️",
    "Транспорт": "🚌",
    "Будинок": "🏠",
    "Догляд": "💄",
    "Шопінг": "🛍️",
    "Кафе та ресторани": "🍽️",
    "Відпочинок": "🏖️",
    "Домашні улюбленці": "🐶",
    "Подарунки": "🎁",
    "Зарплата": "💰",
    "Перекази": "💳",
    "Інше": "📁"
}

def get_category_keyboard(categories_data: list[dict], show_manage_buttons: bool = True):
    """
    Динамічно генерує клавіатуру з системних та кастомних категорій.
    """
    keyboard = []
    row = []

    # 1. Додаємо кнопки самих категорій
    for i, cat in enumerate(categories_data, start=1):
        icon = cat.get('icon_emoji') or "📁"
        name = cat['name']
        btn_text = f"{icon} {name}"

        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"category:{name}"))

        # 2 кнопки в ряд
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # 2. Додаємо кнопки управління (Створити / Видалити)
    if show_manage_buttons:
        manage_row = [InlineKeyboardButton(text="➕ Створити власну", callback_data="manage_cat:add")]

        # Перевіряємо, чи є хоча б одна кастомна категорія
        has_custom = any(cat.get('is_custom') for cat in categories_data)
        if has_custom:
            manage_row.append(InlineKeyboardButton(text="🗑️ Видалити власну", callback_data="manage_cat:delete"))

        keyboard.append(manage_row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Ця клавіатура потрібна для режиму видалення (щоб видаляти тільки кастомні)
def get_delete_custom_category_keyboard(categories_data: list[dict]):
    keyboard = []
    for cat in categories_data:
        if cat.get('is_custom'):
            btn_text = f"❌ {cat['name']}"
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"del_cat:{cat['category_id']}")])

    keyboard.append([InlineKeyboardButton(text="🔙 Скасувати", callback_data="manage_cat:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_period_view_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(text="📅 Сьогодні", callback_data="view:today"),
            InlineKeyboardButton(text="🗓️ Тиждень", callback_data="view:week"),
        ],
        [
            InlineKeyboardButton(text="📆 Місяць", callback_data="view:month"),
            InlineKeyboardButton(text="🔁 Обрати період", callback_data="view:custom"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_expense_categories_keyboard(category_sums: dict):
    keyboard = []

    for category, total in sorted(category_sums.items(), key=lambda item: item[1], reverse=True):
        icon = category_icons_map.get(category, "🏷️")
        button = InlineKeyboardButton(
            text=f"{icon} {category} – {total:g} грн",
            callback_data=f"cat:{category}"
        )
        keyboard.append([button])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_to_categories_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back:categories")]
        ]
    )

def get_expense_action_keyboard(expense_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_expense:{expense_id}"),
                InlineKeyboardButton(text="✏️ Редагувати", callback_data=f"edit:{expense_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back:category_expenses")
            ]
        ]
    )

def get_income_list_keyboard(incomes: list[dict]):
    keyboard = []

    for income in incomes:
        amount = float(income["amount"])
        description = " ".join((income.get("description") or "").split())
        if len(description) > 35:
            description = f"{description[:32]}..."

        btn_text = f"💰 {amount:g} грн"
        if description:
            btn_text += f" — {description}"

        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"income:{income['id']}")])

    keyboard.append([InlineKeyboardButton(text="🔙 Назад до звіту", callback_data="back:report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_income_action_keyboard(income_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Видалити прибуток", callback_data=f"delete_income:{income_id}")],
            [InlineKeyboardButton(text="🔙 Назад до прибутків", callback_data="back:incomes")]
        ]
    )

def get_limits_main_keyboard():
    """Головне меню лімітів"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Встановити новий ліміт", callback_data="limit_menu:setup")],
        [InlineKeyboardButton(text="📊 Переглянути мої ліміти", callback_data="limit_menu:view")],
        [InlineKeyboardButton(text="🗓 Налаштувати початок місяця", callback_data="limit_menu:billing_day")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_limit_options_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="🌍 Загальний ліміт (На всі витрати)", callback_data="limit:global")],
        [InlineKeyboardButton(text="📂 Ліміт на конкретну категорію", callback_data="limit:category")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_action")] # <--- ДОДАЛИ
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
