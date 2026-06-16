import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from keyboards.reply import cancel_keyboard
from services.db import DatabaseRepository
from utils.bot_messages import answer_with_main_menu
from utils.constants import TransactionType, DefaultCategory, Emoji

# Налаштовуємо логер для цього файлу
logger = logging.getLogger(__name__)

router = Router()

class AddIncome(StatesGroup):
    waiting_for_amount = State()
    waiting_for_comment = State()

@router.message(F.text == f"💰 Додати прибуток")
async def start_income(message: Message, state: FSMContext):
    await message.answer("Введи суму прибутку (наприклад, 1000.50):", reply_markup=cancel_keyboard())
    await state.set_state(AddIncome.waiting_for_amount)


@router.message(AddIncome.waiting_for_amount)
async def get_income_amount(message: Message, state: FSMContext):
    try:
        # Додамо replace для коми, щоб користувачам було зручніше
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("❗ Будь ласка, введи коректну суму (приклад: 1200.00)")

    await state.update_data(amount=amount)
    await message.answer("Додай коментар до прибутку (необов’язково):")
    await state.set_state(AddIncome.waiting_for_comment)


# ПРИЙМАЄМО db (об'єкт репозиторію) через Dependency Injection
@router.message(AddIncome.waiting_for_comment)
async def save_income_data(message: Message, state: FSMContext, db: DatabaseRepository):
    data = await state.get_data()

    # Викликаємо методи класу db
    await db.check_user_exists(message.from_user.id, message.from_user.username)

    try:
        # Зберігаємо транзакцію в PostgreSQL
        await db.save_transaction(
            user_id=message.from_user.id,
            amount=data["amount"],
            category_name=DefaultCategory.SALARY.value,  # Використовуємо константу
            trans_type=TransactionType.INCOME.value,     # Використовуємо константу
            raw_text=message.text                        # Це коментар користувача
        )

        await answer_with_main_menu(message, f"{Emoji.SUCCESS.value} Прибуток успішно збережено!")
    except Exception as e:
        # Логуємо помилку замість print
        logger.error("Помилка бази даних при збереженні прибутку (User %s): %s", message.from_user.id, e)
        await message.answer(f"{Emoji.WARNING.value} Виникла помилка при збереженні. Спробуйте пізніше.")
    finally:
        await state.clear()
