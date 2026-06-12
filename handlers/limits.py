import logging
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram.types import FSInputFile
from pathlib import Path

from keyboards.inline import get_limit_options_keyboard, get_category_keyboard, get_limits_main_keyboard
from keyboards.reply import main_menu_keyboard, cancel_keyboard
from services.db import DatabaseRepository
from utils.chart import generate_limits_bar_chart
from utils.constants import Emoji

# Налаштовуємо логер
logger = logging.getLogger(__name__)

router = Router()

class SetLimit(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_billing_day = State()


# 1. Ловимо кнопку з головного меню
@router.message(F.text == "⚙️ Налаштування лімітів")
async def start_limit_menu(message: Message):
    await message.answer("Обери дію з бюджетами:", reply_markup=get_limits_main_keyboard())


# ---------------------------------------------------------
# ГІЛКА 1: НАЛАШТУВАННЯ (СТВОРЕННЯ) ЛІМІТІВ
# ---------------------------------------------------------

@router.callback_query(F.data == "limit_menu:setup")
async def start_limit_setup(callback: CallbackQuery):
    await callback.message.edit_text(
        "На який тип витрат ти хочеш встановити ліміт?",
        reply_markup=get_limit_options_keyboard()
    )


@router.callback_query(F.data == "limit:global")
async def global_limit_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Введи максимальну суму витрат на **місяць** (наприклад, 15000):",
                                  parse_mode="Markdown", reply_markup=cancel_keyboard())
    await state.set_state(SetLimit.waiting_for_amount)


@router.callback_query(F.data == "limit:category")
async def category_limit_handler(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    # Використовуємо об'єкт db
    cats = await db.get_all_user_categories(callback.from_user.id)
    await callback.message.edit_text("Обери категорію, на яку хочеш встановити ліміт:", reply_markup=get_category_keyboard(cats))
    await state.set_state(SetLimit.waiting_for_category)


@router.callback_query(F.data.startswith("category:"), SetLimit.waiting_for_category)
async def get_limit_category(callback: CallbackQuery, state: FSMContext):
    category_name = callback.data.split("category:")[1]
    await state.update_data(limit_category=category_name)
    await callback.message.delete()
    await callback.message.answer(f"Введи максимальну суму для категорії **{category_name}**:", parse_mode="Markdown",
                                  reply_markup=cancel_keyboard())
    await state.set_state(SetLimit.waiting_for_amount)


@router.message(SetLimit.waiting_for_amount)
async def save_limit_amount(message: Message, state: FSMContext, db: DatabaseRepository):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount < 0:
            raise ValueError
    except ValueError:
        return await message.answer("❗ Будь ласка, введи коректну суму (0 або більше):")

    data = await state.get_data()
    category_name = data.get("limit_category")

    try:
        category_id = None
        if category_name:
            # Знаходимо ID категорії через метод репозиторію
            category_id = await db.get_category_id_by_name(category_name, message.from_user.id)

        # Викликаємо збереження через db
        await db.set_budget_limit(
            user_id=message.from_user.id,
            target_amount=amount,
            category_id=category_id
        )

        target = "УСІ ВИТРАТИ" if not category_name else f"категорію '{category_name}'"

        if amount == 0:
            await message.answer(f"🗑️ Ліміт на **{target}** успішно видалено!", parse_mode="Markdown", reply_markup=main_menu_keyboard())
        else:
            await message.answer(f"{Emoji.SUCCESS.value} Бюджет успішно встановлено!\nЛіміт на **{target}**: `{amount} грн`", parse_mode="Markdown", reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.error("Помилка при збереженні ліміту для юзера %s: %s", message.from_user.id, e)
        await message.answer(f"{Emoji.WARNING.value} Виникла помилка. Спробуй пізніше.")
    finally:
        await state.clear()


# ---------------------------------------------------------
# ГІЛКА 2: ПЕРЕГЛЯД ЛІМІТІВ
# ---------------------------------------------------------

@router.callback_query(F.data == "limit_menu:view")
async def view_limits_handler(callback: CallbackQuery, db: DatabaseRepository):
    user_id = callback.from_user.id
    await callback.message.delete()
    msg = await callback.message.answer("⏳ Збираю дані та малюю графік лімітів...")

    try:
        # Використовуємо db
        limits_data = await db.get_all_limits_status(user_id)

        if not limits_data:
            await msg.edit_text("🤷‍♂️ Ти ще не встановив жодного ліміту.\nОбери 'Встановити новий ліміт' у меню.")
            return

        billing_day = await db.get_user_billing_day(user_id)
        start_date, end_date = db.get_financial_period(billing_day)
        period_text = f"Період: {start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')}"

        chart_path = Path(f"limits_chart_{user_id}.png")
        generate_limits_bar_chart(limits_data, period_text, file_path=str(chart_path))

        photo = FSInputFile(path=str(chart_path))
        await callback.message.answer_photo(
            photo=photo,
            caption="📊 **Ваші поточні ліміти:**",
            parse_mode="Markdown"
        )
        await msg.delete()

    except Exception as e:
        logger.error("Помилка генерації графіка лімітів для юзера %s: %s", user_id, e)
        await msg.edit_text(f"{Emoji.WARNING.value} Виникла помилка при побудові графіка.")


# ---------------------------------------------------------
# ГІЛКА 3: НАЛАШТУВАННЯ ДНЯ ПОЧАТКУ МІСЯЦЯ
# ---------------------------------------------------------

@router.callback_query(F.data == "limit_menu:billing_day")
async def start_billing_day_setup(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Обери в календарі день, з якого починається твій фінансовий місяць "
        "(наприклад, день зарплати). Усі ліміти будуть обнулятися саме в цей день щомісяця.\n\n"
        "*(Місяць та рік не мають значення, бот запам'ятає лише вибране ЧИСЛО)*:",
        parse_mode="Markdown",
        reply_markup=await SimpleCalendar().start_calendar()
    )
    await state.set_state(SetLimit.waiting_for_billing_day)


@router.callback_query(SimpleCalendarCallback.filter(), SetLimit.waiting_for_billing_day)
async def process_billing_day_calendar(callback: CallbackQuery, callback_data: dict, state: FSMContext, db: DatabaseRepository):
    result, selected_date = await SimpleCalendar().process_selection(callback, callback_data)

    if result:
        day = selected_date.day

        try:
            # Використовуємо db
            await db.update_user_billing_day(callback.from_user.id, day)

            await callback.message.edit_text(
                f"{Emoji.SUCCESS.value} Готово! Тепер твій фінансовий місяць починатиметься **{day}-го числа**.",
                parse_mode="Markdown",
                reply_markup=get_limits_main_keyboard()
            )
        except Exception as e:
            logger.error("Помилка при оновленні billing_day для юзера %s: %s", callback.from_user.id, e)
            await callback.message.edit_text(f"{Emoji.WARNING.value} Помилка збереження.")
        finally:
            await state.clear()