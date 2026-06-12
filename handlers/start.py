import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from keyboards.reply import main_menu_keyboard
from services.db import DatabaseRepository

logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
async def start_handler(message: Message, db: DatabaseRepository):
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

    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


@router.message(F.text.in_(["Скасувати", "❌ Скасувати", "cancel", "/cancel"]))
async def cancel_handler(message: Message, state: FSMContext):
    """Дозволяє користувачу перервати будь-яку дію в будь-який момент."""
    current_state = await state.get_state()
    if current_state is None:
        return  # Якщо стану немає, просто ігноруємо

    await state.clear()
    await message.answer("Дію скасовано. 🚫", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "cancel_action")
async def cancel_action_callback(callback: CallbackQuery, state: FSMContext):
    """Обробляє Інлайн-кнопку скасування."""
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()

    await callback.message.delete()  # Видаляємо меню з кнопками, щоб очистити чат
    await callback.message.answer("Дію скасовано. 🚫", reply_markup=main_menu_keyboard())
    await callback.answer()