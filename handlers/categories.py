import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.db import DatabaseRepository
from keyboards.inline import get_category_keyboard, get_delete_custom_category_keyboard
from keyboards.reply import cancel_keyboard
from utils.constants import MAX_CUSTOM_CATEGORIES, Emoji


logger = logging.getLogger(__name__)
router = Router()


class ManageCategory(StatesGroup):
    waiting_for_new_name = State()


# 1. НАТИСКАННЯ НА "СТВОРИТИ ВЛАСНУ"
@router.callback_query(F.data == "manage_cat:add")
async def start_add_custom_category(callback: CallbackQuery, state: FSMContext, db: DatabaseRepository):
    user_id = callback.from_user.id

    try:
        custom_count = await db.count_custom_categories(user_id)

        if custom_count >= MAX_CUSTOM_CATEGORIES:
            await callback.answer(
                f"❗ Досягнуто ліміт! Можна створити не більше {MAX_CUSTOM_CATEGORIES} власних категорій.",
                show_alert=True)
            return

        # === ОСЬ ТУТ ВИПРАВЛЕНО ===
        # 1. Спочатку видаляємо повідомлення з інлайн-кнопками
        await callback.message.delete()

        # 2. Відправляємо НОВЕ повідомлення, до якого можна прикріпити велику кнопку "Скасувати"
        await callback.message.answer(
            "Введи назву для нової категорії (наприклад, 'Ремонт авто'):",
            reply_markup=cancel_keyboard()
        )
        # ==========================

        await state.set_state(ManageCategory.waiting_for_new_name)
    except Exception as e:
        logger.error("Помилка при перевірці ліміту категорій для юзера %s: %s", user_id, e)
        await callback.answer(f"{Emoji.WARNING.value} Виникла системна помилка.", show_alert=True)

# 2. ЗБЕРЕЖЕННЯ НОВОЇ КАТЕГОРІЇ
@router.message(ManageCategory.waiting_for_new_name)
async def save_custom_category(message: Message, state: FSMContext, db: DatabaseRepository):
    new_name = message.text.strip()

    if len(new_name) > 30:
        return await message.answer("❗ Назва занадто довга. Введи коротшу назву:")

    try:
        success = await db.add_custom_category(message.from_user.id, new_name)

        if success:
            # 1. Замість того, щоб знову видавати сітку категорій, ми просто
            # повідомляємо про успіх і повертаємо Головне Меню (що автоматично затре кнопку "Скасувати").
            from keyboards.reply import main_menu_keyboard  # Переконайся, що імпорт є

            await message.answer(
                f"{Emoji.SUCCESS.value} Категорію '{new_name}' успішно створено!\n"
                f"Тепер ти можеш використовувати її при додаванні витрат.",
                reply_markup=main_menu_keyboard()
            )
        else:
            from keyboards.reply import main_menu_keyboard
            await message.answer(
                f"{Emoji.WARNING.value} Помилка створення або досягнуто ліміту.",
                reply_markup=main_menu_keyboard()
            )
    except Exception as e:
        logger.error("Помилка при створенні категорії '%s' юзером %s: %s", new_name, message.from_user.id, e)
        await message.answer(f"{Emoji.WARNING.value} Виникла помилка. Спробуй пізніше.")
    finally:
        await state.clear()


# 3. НАТИСКАННЯ НА "ВИДАЛИТИ ВЛАСНУ"
@router.callback_query(F.data == "manage_cat:delete")
async def start_delete_custom_category(callback: CallbackQuery, db: DatabaseRepository):
    user_id = callback.from_user.id

    try:
        cats = await db.get_all_user_categories(user_id)
        await callback.message.edit_text(
            "Обери категорію, яку хочеш видалити (витрати в ній НЕ видаляться, але категорію не можна буде обрати знову):",
            reply_markup=get_delete_custom_category_keyboard(cats)
        )
    except Exception as e:
        logger.error("Помилка завантаження меню видалення для юзера %s: %s", user_id, e)
        await callback.answer(f"{Emoji.WARNING.value} Сталася помилка.", show_alert=True)


# 4. ВИДАЛЕННЯ КАТЕГОРІЇ З БАЗИ
@router.callback_query(F.data.startswith("del_cat:"))
async def process_delete_custom_category(callback: CallbackQuery, db: DatabaseRepository):
    cat_id = int(callback.data.split("del_cat:")[1])

    try:
        await db.delete_custom_category(callback.from_user.id, cat_id)

        # Повертаємо нормальну клавіатуру
        cats = await db.get_all_user_categories(callback.from_user.id)
        await callback.message.edit_text(f"{Emoji.SUCCESS.value} Категорію видалено. Обери категорію для дії:",
                                         reply_markup=get_category_keyboard(cats))
    except Exception as e:
        logger.error("Помилка при видаленні категорії ID %s юзером %s: %s", cat_id, callback.from_user.id, e)
        await callback.answer(f"{Emoji.WARNING.value} Сталася помилка при видаленні.", show_alert=True)


# 5. Скасування видалення
@router.callback_query(F.data == "manage_cat:cancel")
async def cancel_manage_category(callback: CallbackQuery, db: DatabaseRepository):
    try:
        cats = await db.get_all_user_categories(callback.from_user.id)
        await callback.message.edit_text("Обери категорію:", reply_markup=get_category_keyboard(cats))
    except Exception as e:
        logger.error("Помилка при скасуванні видалення юзером %s: %s", callback.from_user.id, e)
        await callback.message.delete()  # Просто видаляємо повідомлення, якщо щось пішло не так