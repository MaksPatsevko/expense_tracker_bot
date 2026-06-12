from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard():
    # Робимо красиву дворівневу клавіатуру (по 2 кнопки в ряд)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➖ Додати витрату"),
                KeyboardButton(text="➕ Додати прибуток")
            ],
            [
                KeyboardButton(text="⏱️ Переглянути витрати"),
                KeyboardButton(text="💳 Прив'язати банківський рахунок") # НОВА КНОПКА ТУТ!
            ],
            [
                KeyboardButton(text="⚙️ Налаштування лімітів")
            ]
        ],
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

