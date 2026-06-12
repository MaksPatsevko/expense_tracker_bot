import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.monobank import setup_monobank_webhook
from utils.constants import Emoji

logger = logging.getLogger(__name__)
router = Router()


class AddMonoAccount(StatesGroup):
    waiting_for_token = State()


@router.message(F.text.contains("💳 Прив'язати банківський рахунок"))
async def accounts_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 Підключити Monobank", callback_data="add_mono")],
        [InlineKeyboardButton(text="❌ Як відключити Monobank?", callback_data="remove_mono")]
    ])
    await message.answer("Тут ти можеш керувати інтеграцією з банківськими рахунками.", reply_markup=keyboard)


@router.callback_query(F.data == "add_mono")
async def process_add_mono(callback: CallbackQuery, state: FSMContext):
    instruction_text = (
        "Щоб бот міг автоматично записувати Ваші витрати, підключіть Monobank.\n\n"
        "1. Перейдіть за посиланням: https://api.monobank.ua/\n"
        "2. Авторизуйтесь через додаток Mono.\n"
        "3. Скопіюйте ваш **Особистий токен**.\n"
        "4. Відправте його сюди в чат ⬇️"
    )

    await callback.message.edit_text(
        instruction_text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_accounts_menu")]
        ])
    )

    await state.set_state(AddMonoAccount.waiting_for_token)


@router.message(AddMonoAccount.waiting_for_token)
async def save_mono_token(message: Message, state: FSMContext):
    token = message.text.strip()
    user_id = message.from_user.id

    msg = await message.answer("🔄 Підключаюсь до Monobank...")

    try:
        success = await setup_monobank_webhook(token, user_id)

        if success:
            await msg.edit_text(
                f"{Emoji.SUCCESS.value} **Monobank успішно підключено!**\nТепер всі твої витрати будуть автоматично зберігатися сюди.",
                parse_mode="Markdown"
            )
            logger.info("Користувач %s успішно підключив Monobank.", user_id)
        else:
            await msg.edit_text(f"{Emoji.WARNING.value} Помилка підключення. Перевір токен і спробуй ще раз.")
            logger.warning("Користувачу %s не вдалося підключити Monobank (можливо, невірний токен).", user_id)

    except Exception as e:
        logger.error("Критична помилка при підключенні Monobank для користувача %s: %s", user_id, e)
        await msg.edit_text(f"{Emoji.CRITICAL.value} Виникла системна помилка при підключенні. Спробуйте пізніше.")
    finally:
        await state.clear()


@router.callback_query(F.data == "remove_mono")
async def process_remove_mono(callback: CallbackQuery):
    instruction_text = (
        "🔒 **Щоб відключити автоматичний облік Monobank:**\n\n"
        "Оскільки бот не зберігає твої ключі безпеки, відключення відбувається на стороні самого банку.\n\n"
        "1. Перейди за посиланням: https://api.monobank.ua/\n"
        "2. Авторизуйся через додаток Mono.\n"
        "3. Натисни кнопку **«Відкликати токен»**.\n\n"
        "*Після цього банк гарантовано припинить надсилати будь-які дані.*"
    )

    await callback.message.edit_text(
        instruction_text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_accounts_menu")]
        ])
    )


@router.callback_query(F.data == "back_to_accounts_menu")
async def back_to_accounts(callback: CallbackQuery, state: FSMContext):
    # Очищаємо стан, щоб бот більше не чекав на токен!
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 Підключити Monobank", callback_data="add_mono")],
        [InlineKeyboardButton(text="❌ Як відключити Monobank?", callback_data="remove_mono")]
    ])
    await callback.message.edit_text(
        "Тут ти можеш керувати інтеграцією з банківськими рахунками.",
        reply_markup=keyboard
    )
