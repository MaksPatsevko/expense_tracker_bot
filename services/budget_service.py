import logging
from services.db import DatabaseRepository
from utils.constants import Emoji

logger = logging.getLogger(__name__)


async def check_and_generate_limit_alert(
        db: DatabaseRepository,
        user_id: int,
        current_transaction_amount: float,
        category_id: int = None,
        category_name: str = None
) -> str | None:
    """
    Перевіряє, чи не перетнула сума витрат певні пороги (50%, 75%, 90%, 100%).
    Повертає текст попередження або None.
    """
    try:
        # Викликаємо методи об'єкта репозиторію
        limit = await db.get_budget_limit(user_id, category_id)
        if not limit or limit <= 0:
            return None

        # Отримуємо суму ВСІХ витрат за індивідуальний місяць
        new_spent = await db.get_current_spent(user_id, category_id)

        # Скільки було витрачено ДО цієї транзакції
        old_spent = new_spent - current_transaction_amount

        new_percentage = (new_spent / limit) * 100
        old_percentage = (old_spent / limit) * 100

        target_name = f"*{category_name}*" if category_name else "*Загального бюджету*"
        limit_str = f"{limit:g}"

        alert_text = None

        # ПЕРЕВІРКА ПЕРЕТИНУ ПОРОГІВ
        if old_percentage < 100 and new_percentage >= 100:
            alert_text = f"{Emoji.CRITICAL.value} **КРИТИЧНО!** Вичерпано 100% ліміту для {target_name} ({limit_str} грн)."

        elif old_percentage < 90 and 90 <= new_percentage < 100:
            alert_text = f"{Emoji.WARNING.value} **УВАГА!** Використано {new_percentage:.0f}% ліміту для {target_name}. Залишилось: `{limit - new_spent:g} грн`."

        elif old_percentage < 75 and 75 <= new_percentage < 90:
            alert_text = f"🟡 **Обережно!** Використано {new_percentage:.0f}% ліміту для {target_name}."

        elif old_percentage < 50 and 50 <= new_percentage < 75:
            alert_text = f"{Emoji.INFO.value} **Інфо:** Ви використали половину ліміту для {target_name}."

        return alert_text

    except Exception as e:
        logger.error("Помилка генерації алертів для юзера %s: %s", user_id, e)
        return None