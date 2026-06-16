import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from services.db import DatabaseRepository
from services.test_data_service import seed_test_data
from utils.bot_messages import answer_with_main_menu


logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext, db: DatabaseRepository):
    await state.clear()

    try:
        await db.check_user_exists(message.from_user.id, message.from_user.username)
    except Exception as e:
        logger.error("Помилка при реєстрації користувача ID %s: %s", message.from_user.id, e)

    welcome_text = (
        f"Привіт, {message.from_user.first_name}! 👋\n\n"
        "Я — чат-бот для контролю за власними фінансами. Я допоможу тобі легко контролювати бюджет.\n\n"
        "🤖 **Як мною користуватися?**\n"
        "Тобі більше не треба натискати купу кнопок! Просто напиши мені свої витрати або доходи звичайним текстом, і я сам усе зрозумію.\n\n"
        "📝 *Приклади:*\n"
        "• `Кава 65`\n"
        "• `Купив продукти в Сільпо на 1250.50`\n"
        "• `Аванс 15000`\n"
        "• `Таксі 200`\n\n"
        "Також ти можеш використовувати меню нижче для перегляду аналітики та детальних звітів ⬇️"
    )

    welcome_text = (
        f"Вітаю, {message.from_user.first_name}! 👋\n\n"
        "Я — чат-бот для контролю за власними фінансами. "
        "Я допоможу Вам зручно вести облік витрат, доходів і контролювати бюджет.\n\n"
        "🤖 **Як користуватися ботом?**\n"
        "Вам більше не треба натискати купу кнопок! Просто напишіть мені свої витрати або доходи звичайним текстом, і я сам усе зрозумію.\n\n"
        "📝 *Приклади:*\n"
        "• `Кава 65`\n"
        "• `Купив продукти в Сільпо на 1250.50`\n"
        "• `Аванс 15000`\n"
        "• `Таксі 200`\n\n"
        "Також Ви можете використовувати меню нижче для перегляду аналітики, "
        "детальних звітів, експорту даних та налаштування бюджетних лімітів. ⬇️\n\n"
        "Для перегляду доступних команд напишіть /help."
    )

    await answer_with_main_menu(message, welcome_text, parse_mode="Markdown")

@router.message(Command("help"))
async def help_handler(message: Message):
    help_text = (
        "ℹ️ <b>Довідка</b>\n\n"
        "Я допомагаю вести облік особистих фінансів: витрат, прибутків, "
        "бюджетних лімітів та фінансових звітів.\n\n"
        "<b>Доступні команди:</b>\n"
        "<code>/start</code> — почати роботу з ботом\n"
        "<code>/help</code> — переглянути довідку\n"
        "<code>/menu</code> — відкрити головне меню\n"
        "<code>/cancel</code> — скасувати поточну дію\n"
        "<code>/reset_data</code> — видалити всі Ваші фінансові дані\n\n"
        "<b>Швидке додавання операцій:</b>\n"
        "Ви можете просто написати фінансову операцію звичайним текстом:\n"
        "• <code>Кава 65</code>\n"
        "• <code>Таксі 200</code>\n"
        "• <code>Купив продукти в Сільпо на 1250.50</code>\n"
        "• <code>Аванс 15000</code>\n\n"
        "Також усі основні дії доступні через меню нижче."
    )

    await answer_with_main_menu(message, help_text, parse_mode="HTML")

@router.message(Command("menu"))
async def menu_handler(message: Message):
    await answer_with_main_menu(message, "Меню оновлено.")


@router.message(Command("reset_keyboard"))
async def reset_keyboard_handler(message: Message):
    await message.answer(
        "Клавіатуру скинуто. Зараз відкрию головне меню заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    await answer_with_main_menu(message, "Меню оновлено.")

@router.message(F.text.in_(["Скасувати", "❌ Скасувати", "cancel", "/cancel"]))
async def cancel_handler(message: Message, state: FSMContext):
    """Дозволяє користувачу перервати будь-яку дію в будь-який момент."""
    current_state = await state.get_state()
    if current_state is None:
        return  # Якщо стану немає, просто ігноруємо

    await state.clear()
    await answer_with_main_menu(message, "Дію скасовано. 🚫")


@router.callback_query(F.data == "cancel_action")
async def cancel_action_callback(callback: CallbackQuery, state: FSMContext):
    """Обробляє Інлайн-кнопку скасування."""
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()

    await callback.message.delete()  # Видаляємо меню з кнопками, щоб очистити чат
    await answer_with_main_menu(callback.message, "Дію скасовано. 🚫")
    await callback.answer()

@router.message(Command("reset_data"))
async def reset_data_handler(message: Message, state: FSMContext):
    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Так, видалити всі дані", callback_data="reset_data:confirm")],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="reset_data:cancel")]
        ]
    )

    await message.answer(
        "⚠️ **Видалення даних**\n\n"
        "Ви дійсно хочете видалити всі свої фінансові дані?\n\n"
        "Будуть видалені витрати, прибутки, рахунки, бюджетні ліміти та власні категорії.\n\n"
        "**Цю дію неможливо скасувати.**",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "reset_data:cancel")
async def cancel_reset_data(callback: CallbackQuery):
    await callback.message.delete()
    await answer_with_main_menu(callback.message, "Видалення даних скасовано. ✅")
    await callback.answer()


@router.callback_query(F.data == "reset_data:confirm")
async def confirm_reset_data(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    await state.clear()

    try:
        await db.reset_user_data(callback.from_user.id)

        await callback.message.edit_text(
            "✅ Ваші фінансові дані успішно видалено."
        )
        await answer_with_main_menu(callback.message, "Можете почати облік заново з головного меню ⬇️")

    except Exception as e:
        logger.error("Помилка очищення даних користувача %s: %s", callback.from_user.id, e)
        await callback.message.edit_text(
            "⚠️ Виникла помилка під час видалення даних. Спробуйте пізніше."
        )

    await callback.answer()

@router.message(Command("test_data"))
async def test_data_handler(message: Message, state: FSMContext, db: DatabaseRepository):
    await state.clear()

    msg = await message.answer("⏳ Створюю тестові дані для демонстрації...")

    try:
        result = await seed_test_data(
            db=db,
            user_id=message.from_user.id,
            username=message.from_user.username
        )

        start_text = result["start_date"].strftime("%d.%m.%Y")
        end_text = result["end_date"].strftime("%d.%m.%Y")

        await msg.edit_text(
            "✅ Тестові дані успішно створено.\n\n"
            f"Період: {start_text} - {end_text}\n"
            f"Категорій витрат: {result['category_count']}\n"
            f"Витрат: {result['expense_count']}\n"
            f"Прибутків: {result['income_count']}\n"
            "Ліміти: загальний та по категоріях."
        )

        await answer_with_main_menu(message, "Можете перейти до перегляду звіту через меню нижче ⬇️")

    except Exception as e:
        logger.error("Помилка створення тестових даних для користувача %s: %s", message.from_user.id, e)
        await msg.edit_text("⚠️ Не вдалося створити тестові дані.")
