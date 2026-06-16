import logging
from datetime import datetime, timedelta
import os
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from keyboards.inline import (
    get_category_keyboard,
    get_period_view_keyboard,
    get_expense_action_keyboard,
    get_back_to_categories_keyboard,
    get_income_list_keyboard,
    get_income_action_keyboard
)
from keyboards.reply import cancel_keyboard, optional_description_keyboard
from services.db import DatabaseRepository
from services.nlp_parser import parse_transaction_text_ai
from services.budget_service import check_and_generate_limit_alert
from services.report import build_period_report
from services.transaction_service import process_and_save_transaction
from services.export_service import generate_csv_report
from utils.bot_messages import answer_with_main_menu
from utils.constants import TransactionType, DefaultCategory, Emoji

logger = logging.getLogger(__name__)
router = Router()

def ua_calendar():
    return SimpleCalendar(
        locale="uk_UA",
        cancel_btn="Скасувати",
        today_btn="Сьогодні"
    )

@router.message(StateFilter(None), F.text & ~F.text.startswith("/") & ~F.text.in_(["💸 Додати витрату", "💰 Додати прибуток", "⏱️ Переглянути витрати", "💳 Прив'язати банківський рахунок", "⚙️ Налаштування лімітів"]))
async def process_nlp_transaction(message: Message, state: FSMContext, db: DatabaseRepository):
    cats_data = await db.get_all_user_categories(message.from_user.id, TransactionType.EXPENSE.value)
    user_categories = [c['name'] for c in cats_data]

    parsed_data = await parse_transaction_text_ai(message.text, user_categories)

    if not parsed_data:
        return await message.answer(
            "Не зміг розпізнати фінансову операцію. 🤷‍♂️\n"
            "Напишіть суму та призначення (наприклад: *Кава 150*) або скористайтеся меню нижче.",
            parse_mode="Markdown"
        )

    if parsed_data['type'] == TransactionType.INCOME.value:
        parsed_data['category'] = DefaultCategory.SALARY.value
    elif parsed_data['category'] is None:
        parsed_data['category'] = DefaultCategory.OTHER.value

    # ВИКЛИК СЕРВІСУ!
    response_text = await process_and_save_transaction(
        db=db,
        user_id=message.from_user.id,
        amount=parsed_data['amount'],
        category_name=parsed_data['category'],
        trans_type=parsed_data['type'],
        description=parsed_data['description'],
        source_name="OpenAI"
    )

    if (
            parsed_data['type'] == TransactionType.EXPENSE.value
            and parsed_data['category'] == DefaultCategory.OTHER.value
    ):
        response_text += "\n*(Категорію можна змінити в меню 'Переглянути витрати')*"

    await answer_with_main_menu(message, response_text, parse_mode="Markdown")

# =====================================================================
# СЦЕНАРІЙ 2: КЛАСИЧНИЙ ВВІД ЧЕРЕЗ КНОПКИ (FSM)
# =====================================================================

class AddExpense(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_description = State()

class EditExpense(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_description = State()

class CustomPeriod(StatesGroup):
    waiting_for_start = State()
    waiting_for_end = State()

@router.message(F.text == "💸 Додати витрату")
async def start_add(message: Message, state: FSMContext):
    await message.answer("Введи суму витрати (наприклад, 150.50):", reply_markup=cancel_keyboard())
    await state.set_state(AddExpense.waiting_for_amount)

@router.message(AddExpense.waiting_for_amount)
async def get_amount(message: Message, state: FSMContext, db: DatabaseRepository):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0: raise ValueError
    except ValueError:
        return await message.answer(f"{Emoji.WARNING.value} Будь ласка, введи коректну суму (приклад: 120.50)")

    await state.update_data(amount=amount)

    cats = await db.get_all_user_categories(message.from_user.id, TransactionType.EXPENSE.value)
    await message.answer("📁 Вибери категорію:", reply_markup=get_category_keyboard(cats, show_manage_buttons=False))

    await state.set_state(AddExpense.waiting_for_category)

@router.callback_query(F.data.startswith("category:"), AddExpense.waiting_for_category)
async def get_category_callback(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("category:")[1]
    await state.update_data(category=category)
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "Короткий опис витрати (необов’язково):",
        reply_markup=optional_description_keyboard()
    )
    await state.set_state(AddExpense.waiting_for_description)


@router.message(AddExpense.waiting_for_description)
async def get_description(message: Message, state: FSMContext, db: DatabaseRepository):
    data = await state.get_data()

    description = message.text.strip()
    if description in ["-", "Без опису"]:
        description = ""

    response_text = await process_and_save_transaction(
        db=db,
        user_id=message.from_user.id,
        amount=data["amount"],
        category_name=data["category"],
        trans_type=TransactionType.EXPENSE.value,
        description=description,
        source_name="Ручний ввід"
    )

    await answer_with_main_menu(message, response_text, parse_mode="Markdown")
    await state.clear()


@router.message(F.text == "⏱️ Переглянути витрати")
async def view_expenses(message: Message):
    await message.answer(
        "Оберіть період для перегляду витрат:",
        reply_markup=get_period_view_keyboard()
    )


@router.callback_query(F.data.startswith("view:"))
async def handle_period_selection(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    period = callback.data.split("view:")[1]
    today = datetime.now().date()

    if period == "today":
        start = end = today
    elif period == "week":
        start = today - timedelta(days=6)
        end = today
    elif period == "month":
        billing_day = await db.get_user_billing_day(callback.from_user.id)
        start, end = db.get_financial_period(billing_day)
    elif period == "custom":
        await callback.message.edit_text(
            "Оберіть *початкову дату*:",
            parse_mode="Markdown",
            reply_markup=await ua_calendar().start_calendar()
        )
        await state.set_state(CustomPeriod.waiting_for_start)
        return
    else:
        await callback.answer(f"{Emoji.WARNING.value} Невідомий період", show_alert=True)
        return

    # Зберігаємо обраний період у FSM
    await state.update_data(start_date=start.isoformat(), end_date=end.isoformat())

    try:
        # ЗМІНЕНО: Тепер приймаємо chart_files (це список)
        text, reply_markup, chart_files = await build_period_report(db, callback.from_user.id, start, end)

        # Оновлюємо текст з кнопками
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

        # ЗМІНЕНО: Видаляємо старі фотографії (тепер це може бути масив ID)
        data = await state.get_data()
        last_media_group_ids = data.get("last_media_group_ids", [])

        # Для зворотної сумісності (якщо в пам'яті висить ще старий одиночний ID)
        old_chart_id = data.get("last_chart_message_id")
        if old_chart_id and old_chart_id not in last_media_group_ids:
            last_media_group_ids.append(old_chart_id)

        for msg_id in last_media_group_ids:
            try:
                await callback.bot.delete_message(callback.message.chat.id, msg_id)
            except Exception:
                pass

        # ЗМІНЕНО: Відправляємо нові фото (одне або альбом)
        if chart_files:
            if len(chart_files) == 1:
                # Якщо період "Сьогодні" - картинка одна
                photo_msg = await callback.message.answer_photo(chart_files[0])
                await state.update_data(last_media_group_ids=[photo_msg.message_id])
            else:
                # Якщо картинок більше 1 (Тиждень/Місяць) - формуємо Альбом
                media_group = MediaGroupBuilder()
                for file in chart_files:
                    media_group.add_photo(media=file)

                # Відправляємо альбом
                msgs = await callback.message.answer_media_group(media=media_group.build())
                # Зберігаємо ID всіх повідомлень альбому, щоб потім їх видалити при оновленні звіту
                await state.update_data(last_media_group_ids=[m.message_id for m in msgs])

    except Exception as e:
        logger.error("Помилка генерації звіту для юзера %s: %s", callback.from_user.id, e)
        await callback.message.edit_text(f"{Emoji.WARNING.value} Помилка генерації звіту.")

def build_expense_button_text(exp: dict) -> str:
    amount = float(exp["amount"])
    amount_text = f"{amount:.0f}" if amount.is_integer() else f"{amount:.2f}"

    desc = " ".join((exp.get("description") or "").split())
    if len(desc) > 25:
        desc = f"{desc[:22]}..."

    expense_date = exp.get("date")
    date_text = expense_date.strftime("%d.%m | %H:%M") if expense_date else ""

    if desc:
        return f"{amount_text} грн — {desc} ({date_text})"

    return f"{amount_text} грн ({date_text})"

@router.callback_query(SimpleCalendarCallback.filter(), CustomPeriod.waiting_for_start)
async def process_start_calendar(callback: CallbackQuery, callback_data: dict, state: FSMContext):
    if callback_data.act == "TODAY":
        selected_date = datetime.now()

        await state.update_data(start=selected_date)
        await callback.message.edit_text(
            "Оберіть *кінцеву дату*:",
            parse_mode="Markdown",
            reply_markup=await ua_calendar().start_calendar()
        )
        await state.set_state(CustomPeriod.waiting_for_end)
        await callback.answer()
        return

    result, selected_date = await ua_calendar().process_selection(callback, callback_data)

    if result:
        await state.update_data(start=selected_date)
        await callback.message.edit_text(
            "Оберіть *кінцеву дату*:",
            parse_mode="Markdown",
            reply_markup=await ua_calendar().start_calendar()
        )
        await state.set_state(CustomPeriod.waiting_for_end)


@router.callback_query(SimpleCalendarCallback.filter(), CustomPeriod.waiting_for_end)
async def process_end_calendar(callback: CallbackQuery, callback_data: dict, state: FSMContext, db: DatabaseRepository):
    if callback_data.act == "TODAY":
        result = True
        selected_end = datetime.now()
    else:
        result, selected_end = await ua_calendar().process_selection(callback, callback_data)

    if result:
        selected_end = selected_end.date()
        data = await state.get_data()
        start_date = data.get("start")

        if isinstance(start_date, datetime):
            start_date = start_date.date()

        if selected_end < start_date:
            await callback.message.edit_text(
                f"{Emoji.WARNING.value} Кінцева дата не може бути раніше за початкову. Спробуйте ще раз:",
                reply_markup=await ua_calendar().start_calendar()
            )
            await callback.answer()
            return

        await state.update_data(
            start_date=start_date.isoformat(),
            end_date=selected_end.isoformat()
        )

        try:
            text, reply_markup, chart_files = await build_period_report(
                db,
                callback.from_user.id,
                start_date,
                selected_end
            )

            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

            data = await state.get_data()
            last_media_group_ids = data.get("last_media_group_ids", [])

            old_chart_id = data.get("last_chart_message_id")
            if old_chart_id and old_chart_id not in last_media_group_ids:
                last_media_group_ids.append(old_chart_id)

            for msg_id in last_media_group_ids:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, msg_id)
                except Exception:
                    pass

            if chart_files:
                if len(chart_files) == 1:
                    photo_msg = await callback.message.answer_photo(chart_files[0])
                    await state.update_data(last_media_group_ids=[photo_msg.message_id])
                else:
                    media_group = MediaGroupBuilder()
                    for file in chart_files:
                        media_group.add_photo(media=file)

                    msgs = await callback.message.answer_media_group(media=media_group.build())
                    await state.update_data(last_media_group_ids=[m.message_id for m in msgs])

            await callback.answer()

        except Exception as e:
            logger.error("Помилка генерації звіту з календаря (User %s): %s", callback.from_user.id, e)
            await callback.message.edit_text(f"{Emoji.WARNING.value} Помилка генерації звіту.")
            await callback.answer()

@router.callback_query(F.data.startswith("cat:"))
async def handle_category_click(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    category = callback.data.split("cat:")[1]
    data = await state.get_data()

    if "start_date" not in data or "end_date" not in data:
        return await callback.message.answer(
            f"{Emoji.WARNING.value} Обери період перегляду перед фільтрацією за категоріями."
        )

    start = datetime.fromisoformat(data["start_date"]).date()
    end = datetime.fromisoformat(data["end_date"]).date()

    start_text = start.strftime("%d.%m.%Y")
    end_text = end.strftime("%d.%m.%Y")

    try:
        transactions = await db.get_transactions_by_period(
            user_id=callback.from_user.id,
            start_date=start,
            end_date=end,
            trans_type=TransactionType.EXPENSE.value
        )

        filtered = [t for t in transactions if t["category"] == category]

        if not filtered:
            return await callback.message.answer(
                f"💸 У категорії *{category}* витрат не знайдено.",
                parse_mode="Markdown"
            )

        await state.update_data(current_category=category)

        keyboard = []
        for exp in filtered:
            btn_text = build_expense_button_text(exp)
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"expense:{exp['id']}")])

        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back:categories")])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(
            f"📂 Витрати у категорії *{category}* з {start_text} по {end_text}:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error("Помилка фільтрації за категорією (User %s): %s", callback.from_user.id, e)
        await callback.answer(f"{Emoji.WARNING.value} Системна помилка", show_alert=True)

@router.callback_query(F.data == "back:categories")
async def handle_back_to_categories(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    data = await state.get_data()

    start_str = data.get("start_date")
    end_str = data.get("end_date")

    if not start_str or not end_str:
        return await callback.message.edit_text(f"{Emoji.WARNING.value} Спочатку обери період.")

    start = datetime.fromisoformat(start_str).date()
    end = datetime.fromisoformat(end_str).date()

    try:
        # ЗМІНЕНО: Приймаємо список chart_files
        text, reply_markup, chart_files = await build_period_report(db, callback.from_user.id, start, end)

        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

        # ЗМІНЕНО: Видалення попередніх повідомлень (включаючи альбоми)
        data = await state.get_data()
        last_media_group_ids = data.get("last_media_group_ids", [])

        old_chart_id = data.get("last_chart_message_id")
        if old_chart_id and old_chart_id not in last_media_group_ids:
            last_media_group_ids.append(old_chart_id)

        for msg_id in last_media_group_ids:
            try:
                await callback.bot.delete_message(callback.message.chat.id, msg_id)
            except Exception:
                pass

        # ЗМІНЕНО: Відправка нових картинок
        if chart_files:
            if len(chart_files) == 1:
                photo_msg = await callback.message.answer_photo(chart_files[0])
                await state.update_data(last_media_group_ids=[photo_msg.message_id])
            else:
                media_group = MediaGroupBuilder()
                for file in chart_files:
                    media_group.add_photo(media=file)

                msgs = await callback.message.answer_media_group(media=media_group.build())
                await state.update_data(last_media_group_ids=[m.message_id for m in msgs])

    except Exception as e:
        logger.error("Помилка повернення до категорій (User %s): %s", callback.from_user.id, e)
        await callback.message.edit_text(f"{Emoji.WARNING.value} Системна помилка.")


async def get_selected_period(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start_str = data.get("start_date")
    end_str = data.get("end_date")

    if not start_str or not end_str:
        await callback.message.edit_text(f"{Emoji.WARNING.value} Спочатку обери період.")
        return None

    start = datetime.fromisoformat(start_str).date()
    end = datetime.fromisoformat(end_str).date()
    return start, end


async def show_incomes_list(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    period = await get_selected_period(callback, state)
    if not period:
        return False

    start, end = period
    incomes = await db.get_transactions_by_period(
        user_id=callback.from_user.id,
        start_date=start,
        end_date=end,
        trans_type=TransactionType.INCOME.value
    )

    period_text = f"{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}"
    if not incomes:
        await callback.message.edit_text(
            f"💰 Прибутків за період {period_text} не знайдено.",
            reply_markup=get_income_list_keyboard([])
        )
        return True

    total_income = sum(float(income["amount"]) for income in incomes)
    await callback.message.edit_text(
        f"💰 Прибутки за період {period_text}:\n"
        f"Усього: {total_income:.2f} грн\n\n"
        "Обери прибуток, який хочеш видалити:",
        reply_markup=get_income_list_keyboard(incomes)
    )
    return True


@router.callback_query(F.data == "manage_incomes")
async def manage_incomes_handler(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    try:
        await show_incomes_list(callback, state, db)
    except Exception as e:
        logger.error("Помилка перегляду прибутків (User %s): %s", callback.from_user.id, e)
        await callback.message.edit_text(f"{Emoji.WARNING.value} Не вдалося завантажити прибутки.")
    finally:
        await callback.answer()


@router.callback_query(F.data == "back:incomes")
async def back_to_incomes_handler(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    try:
        await show_incomes_list(callback, state, db)
    except Exception as e:
        logger.error("Помилка повернення до списку прибутків (User %s): %s", callback.from_user.id, e)
        await callback.message.edit_text(f"{Emoji.WARNING.value} Не вдалося завантажити прибутки.")
    finally:
        await callback.answer()


@router.callback_query(F.data == "back:report")
async def back_to_report_handler(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    period = await get_selected_period(callback, state)
    if not period:
        await callback.answer()
        return

    start, end = period
    try:
        text, reply_markup, _ = await build_period_report(db, callback.from_user.id, start, end)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logger.error("Помилка повернення до звіту (User %s): %s", callback.from_user.id, e)
        await callback.message.edit_text(f"{Emoji.WARNING.value} Не вдалося оновити звіт.")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("income:"))
async def handle_income_click(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    income_id = callback.data.split("income:")[1]
    period = await get_selected_period(callback, state)
    if not period:
        await callback.answer()
        return

    start, end = period
    try:
        incomes = await db.get_transactions_by_period(
            user_id=callback.from_user.id,
            start_date=start,
            end_date=end,
            trans_type=TransactionType.INCOME.value
        )
        income = next((item for item in incomes if str(item["id"]) == income_id), None)

        if not income:
            await callback.answer(f"{Emoji.WARNING.value} Прибуток не знайдено.", show_alert=True)
            return

        description = (income.get("description") or "").strip()
        description_text = f"\nОпис: {description}" if description else ""

        await callback.message.edit_text(
            f"💰 Прибуток: {float(income['amount']):.2f} грн{description_text}\n\n"
            "Що бажаєш зробити?",
            reply_markup=get_income_action_keyboard(income_id)
        )
        await callback.answer()
    except Exception as e:
        logger.error("Помилка відкриття прибутку (User %s): %s", callback.from_user.id, e)
        await callback.answer(f"{Emoji.WARNING.value} Системна помилка.", show_alert=True)


@router.callback_query(F.data.startswith("delete_income:"))
async def delete_income_handler(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    income_id = int(callback.data.split("delete_income:")[1])

    try:
        deleted = await db.delete_transaction_by_type(
            transaction_id=income_id,
            user_id=callback.from_user.id,
            trans_type=TransactionType.INCOME.value
        )

        if not deleted:
            await callback.answer(f"{Emoji.WARNING.value} Прибуток не знайдено.", show_alert=True)
            return

        logger.info("Користувач %s видалив прибуток %s", callback.from_user.id, income_id)
        await show_incomes_list(callback, state, db)
        await callback.answer("Прибуток видалено.")
    except Exception as e:
        logger.error("Помилка видалення прибутку (User %s): %s", callback.from_user.id, e)
        await callback.answer(f"{Emoji.WARNING.value} Помилка при видаленні.", show_alert=True)

# =====================================================================
# СЦЕНАРІЙ 4: КЕРУВАННЯ ВИТРАТАМИ (РЕДАГУВАННЯ / ВИДАЛЕННЯ)
# =====================================================================

@router.callback_query(F.data == "change_period")
async def change_period_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "Оберіть період для перегляду витрат:",
        reply_markup=get_period_view_keyboard()
    )

@router.callback_query(F.data.startswith("expense:"))
async def handle_expense_click(callback: CallbackQuery):
    expense_id = callback.data.split("expense:")[1]
    await callback.message.edit_text(
        "Що бажаєш зробити з цією витратою?",
        reply_markup=get_expense_action_keyboard(expense_id)
    )

@router.callback_query(F.data == "back:category_expenses")
async def back_to_expense_list(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    data = await state.get_data()
    category = data.get("current_category")
    if not category:
        return await callback.message.answer(f"{Emoji.WARNING.value} Категорія не визначена.")

    start = datetime.fromisoformat(data["start_date"]).date()
    end = datetime.fromisoformat(data["end_date"]).date()

    start_text = start.strftime("%d.%m.%Y")
    end_text = end.strftime("%d.%m.%Y")

    try:
        transactions = await db.get_transactions_by_period(
            user_id=callback.from_user.id,
            start_date=start,
            end_date=end,
            trans_type=TransactionType.EXPENSE.value
        )

        filtered = [t for t in transactions if t["category"] == category]

        keyboard = []
        for exp in filtered:
            btn_text = build_expense_button_text(exp)
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"expense:{exp['id']}")])

        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back:categories")])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(
            f"📂 Витрати у категорії *{category}* з {start_text} по {end_text}:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error("Помилка повернення до списку витрат (User %s): %s", callback.from_user.id, e)
        await callback.answer(f"{Emoji.WARNING.value} Системна помилка.", show_alert=True)

@router.callback_query(F.data.startswith("delete_expense:"))
async def delete_expense_handler(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    expense_id = int(callback.data.split("delete_expense:")[1])

    try:
        await db.delete_transaction(transaction_id=expense_id, user_id=callback.from_user.id)
        logger.info("Користувач %s видалив транзакцію %s", callback.from_user.id, expense_id)
    except Exception as e:
        logger.error("Помилка при видаленні транзакції (User %s): %s", callback.from_user.id, e)
        return await callback.answer(f"{Emoji.WARNING.value} Помилка при видаленні.", show_alert=True)

    data = await state.get_data()
    category = data.get("current_category")
    start = datetime.fromisoformat(data["start_date"]).date()
    end = datetime.fromisoformat(data["end_date"]).date()

    start_text = start.strftime("%d.%m.%Y")
    end_text = end.strftime("%d.%m.%Y")

    try:
        transactions = await db.get_transactions_by_period(
            user_id=callback.from_user.id,
            start_date=start,
            end_date=end,
            trans_type=TransactionType.EXPENSE.value
        )

        filtered = [t for t in transactions if t["category"] == category]

        if not filtered:
            return await callback.message.edit_text(
                f"💸 У категорії *{category}* витрат не знайдено.",
                parse_mode="Markdown",
                reply_markup=get_back_to_categories_keyboard()
            )

        keyboard = []
        for exp in filtered:
            btn_text = build_expense_button_text(exp)
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"expense:{exp['id']}")])

        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back:categories")])
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            f"📂 Витрати в категорії *{category}* з {start_text} по {end_text}:",
            parse_mode="Markdown",
            reply_markup=markup
        )

    except Exception as e:
        logger.error("Помилка оновлення списку після видалення (User %s): %s", callback.from_user.id, e)

@router.callback_query(F.data.startswith("edit:"))
async def start_edit_expense(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    expense_id = callback.data.split("edit:")[1]
    await state.update_data(editing_expense_id=expense_id)

    data = await state.get_data()
    start_str = data.get("start_date")
    end_str = data.get("end_date")

    expense_title = "витрати"

    if start_str and end_str:
        try:
            start = datetime.fromisoformat(start_str).date()
            end = datetime.fromisoformat(end_str).date()

            transactions = await db.get_transactions_by_period(
                user_id=callback.from_user.id,
                start_date=start,
                end_date=end,
                trans_type=TransactionType.EXPENSE.value
            )

            expense = next((item for item in transactions if str(item["id"]) == expense_id), None)

            if expense:
                amount = float(expense["amount"])
                amount_text = f"{amount:.0f}" if amount.is_integer() else f"{amount:.2f}"

                desc = " ".join((expense.get("description") or "").split())
                if desc:
                    expense_title = f"{amount_text} грн — {desc}"
                else:
                    expense_title = f"{amount_text} грн"

        except Exception as e:
            logger.error("Помилка отримання витрати для редагування (User %s): %s", callback.from_user.id, e)

    await delete_saved_charts(callback.bot, callback.message.chat.id, state)

    try:
        await callback.message.edit_text(
            f"✏️ Редагування витрати ({expense_title})"
        )
    except Exception:
        pass

    await callback.message.answer(
        "Введіть нову суму витрати (наприклад, 150.50):",
        reply_markup=cancel_keyboard()
    )

    await state.set_state(EditExpense.waiting_for_amount)
    await callback.answer()


@router.message(EditExpense.waiting_for_amount)
async def edit_amount(message: Message, state: FSMContext, db: DatabaseRepository):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(f"{Emoji.WARNING.value} Будь ласка, введи коректну суму (наприклад: 120.50)")

    await state.update_data(new_amount=amount)

    try:
        cats = await db.get_all_user_categories(message.from_user.id, TransactionType.EXPENSE.value)
        await message.answer("📁 Вибери нову категорію:", reply_markup=get_category_keyboard(cats, show_manage_buttons=False))
        await state.set_state(EditExpense.waiting_for_category)
    except Exception as e:
        logger.error("Помилка отримання категорій для редагування (User %s): %s", message.from_user.id, e)
        await message.answer(f"{Emoji.WARNING.value} Сталася помилка.")


@router.callback_query(F.data.startswith("category:"), EditExpense.waiting_for_category)
async def edit_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("category:")[1]
    await state.update_data(new_category=category)
    await callback.message.edit_reply_markup()
    await callback.message.answer("📝 Тепер введи новий опис (або напиши '-', якщо без опису):")
    await state.set_state(EditExpense.waiting_for_description)

def format_date_ua(value):
    return value.strftime("%d.%m.%Y")

async def delete_saved_charts(bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    last_media_group_ids = list(data.get("last_media_group_ids", []))

    old_chart_id = data.get("last_chart_message_id")
    if old_chart_id and old_chart_id not in last_media_group_ids:
        last_media_group_ids.append(old_chart_id)

    for msg_id in last_media_group_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

    await state.update_data(last_media_group_ids=[], last_chart_message_id=None)

@router.message(EditExpense.waiting_for_description)
async def edit_description(message: Message, state: FSMContext, db: DatabaseRepository):
    data = await state.get_data()

    expense_id = int(data["editing_expense_id"])
    new_amount = data["new_amount"]
    new_category = data["new_category"]

    new_description = message.text.strip()
    if new_description in ["-", "Без опису"]:
        new_description = ""

    start_str = data.get("start_date")
    end_str = data.get("end_date")
    current_category = data.get("current_category")

    try:
        await db.update_transaction(
            transaction_id=expense_id,
            new_amount=new_amount,
            new_category_name=new_category,
            new_description=new_description,
            user_id=message.from_user.id
        )

        await delete_saved_charts(message.bot, message.chat.id, state)

        await state.clear()

        context_to_restore = {}
        if start_str and end_str:
            context_to_restore["start_date"] = start_str
            context_to_restore["end_date"] = end_str
        if current_category:
            context_to_restore["current_category"] = current_category

        if context_to_restore:
            await state.update_data(**context_to_restore)

        await answer_with_main_menu(message, f"{Emoji.SUCCESS.value} Витрату успішно оновлено!")

        if start_str and end_str:
            start = datetime.fromisoformat(start_str).date()
            end = datetime.fromisoformat(end_str).date()

            text, reply_markup, chart_files = await build_period_report(
                db,
                message.from_user.id,
                start,
                end
            )

            await message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

            if chart_files:
                if len(chart_files) == 1:
                    photo_msg = await message.answer_photo(chart_files[0])
                    await state.update_data(last_media_group_ids=[photo_msg.message_id])
                else:
                    media_group = MediaGroupBuilder()
                    for file in chart_files:
                        media_group.add_photo(media=file)

                    msgs = await message.answer_media_group(media=media_group.build())
                    await state.update_data(last_media_group_ids=[m.message_id for m in msgs])

        logger.info("Користувач %s відредагував транзакцію %s", message.from_user.id, expense_id)

    except Exception as e:
        logger.error("Помилка при оновленні транзакції (User %s): %s", message.from_user.id, e)
        await message.answer(f"{Emoji.WARNING.value} Виникла помилка при оновленні бази даних.")

@router.callback_query(F.data.startswith("export_csv:"))
async def export_csv_handler(callback: CallbackQuery, db: DatabaseRepository):
    _, start_str, end_str = callback.data.split(":")

    start_date = datetime.fromisoformat(start_str).date()
    end_date = datetime.fromisoformat(end_str).date()

    user_id = callback.from_user.id

    # Відправляємо повідомлення, що процес пішов
    msg = await callback.message.answer("⏳ Формую CSV звіт...")

    # Генеруємо файл
    file_path = await generate_csv_report(db, user_id, start_date, end_date)

    if file_path and os.path.exists(file_path):
        # Відправляємо файл
        document = FSInputFile(file_path)
        start_str_ua = start_date.strftime('%d.%m.%Y')
        end_str_ua = end_date.strftime('%d.%m.%Y')

        await callback.message.answer_document(
            document=document,
            caption=f"📁 Ваш детальний фінансовий звіт з {start_str_ua} по {end_str_ua}."
        )
        # Видаляємо тимчасове повідомлення та сам файл з сервера (щоб не засмічувати пам'ять)
        await msg.delete()
        os.remove(file_path)
    else:
        await msg.edit_text("⚠️ Виникла помилка при формуванні звіту.")

    await callback.answer()

