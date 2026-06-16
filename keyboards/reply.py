from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard():
    # Робимо красиву дворівневу клавіатуру (по 2 кнопки в ряд)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💸 Додати витрату"),
                KeyboardButton(text="💰 Додати прибуток")
            ],
            [
                KeyboardButton(text="⏱️ Переглянути витрати"),
                KeyboardButton(text="💳 Прив'язати банківський рахунок") # НОВА КНОПКА ТУТ!
            ],
            [
                KeyboardButton(text="⚙️ Налаштування лімітів")
            ]
        ],
        is_persistent=False,
        one_time_keyboard=False,
        selective=False,
        resize_keyboard=True,
        input_field_placeholder="Обери дію або напиши витрату ⬇️"
    )
    return keyboard

def cancel_keyboard():
    """Клавіатура, яка з'являється під час активного діалогу (FSM)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши відповідь або натисни Скасувати"
    )
    return keyboard

def optional_description_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Без опису")],
            [KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Введи опис або натисни Без опису"
    )
    return keyboard

