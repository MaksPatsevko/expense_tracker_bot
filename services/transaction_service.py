# services/transaction_service.py
import logging
from services.db import DatabaseRepository
from services.budget_service import check_and_generate_limit_alert
from utils.constants import TransactionType, AccountName, Emoji

logger = logging.getLogger(__name__)


async def process_and_save_transaction(
        db: DatabaseRepository,
        user_id: int,
        amount: float,
        category_name: str,
        trans_type: str,
        description: str,
        source_name: str = "Бот",
        # ДОДАЛИ ПАРАМЕТР account_name (за замовчуванням Готівка)
        account_name: str = AccountName.CASH.value
) -> str:
    """
    Універсальний сервіс. Зберігає транзакцію в БД, перевіряє ліміти
    і формує фінальний текст відповіді для користувача.
    """
    try:
        # 1. Зберігаємо в БД (ТЕПЕР ПЕРЕДАЄМО account_name!)
        await db.save_transaction(
            user_id=user_id,
            amount=amount,
            category_name=category_name,
            trans_type=trans_type,
            raw_text=description,
            account_name=account_name  # <--- ВИПРАВЛЕНО ТУТ!
        )

        # 2. Формуємо базовий текст
        icon = Emoji.INCOME_ICON.value if trans_type == TransactionType.INCOME.value else Emoji.EXPENSE_ICON.value
        action = "Зараховано" if trans_type == TransactionType.INCOME.value else "Витрачено"

        response_text = (
            f"{Emoji.SUCCESS.value} **Збережено ({source_name}):**\n"
            f"{icon} {action}: `{amount} / {account_name}`\n"  # Додав рахунок у звіт для наочності!
            f"📁 Категорія: `{category_name}`"
        )

        # 3. Перевіряємо ліміти (тільки для витрат)
        if trans_type == TransactionType.EXPENSE.value:
            category_id = await db.get_category_id_by_name(category_name, user_id)

            cat_alert = await check_and_generate_limit_alert(db, user_id, amount, category_id, category_name)
            global_alert = await check_and_generate_limit_alert(db, user_id, amount, None, None)

            if cat_alert: response_text += f"\n\n{cat_alert}"
            if global_alert: response_text += f"\n\n{global_alert}"

        return response_text

    except Exception as e:
        logger.error("Помилка у transaction_service для юзера %s: %s", user_id, e)
        return f"{Emoji.WARNING.value} Виникла помилка при збереженні даних."