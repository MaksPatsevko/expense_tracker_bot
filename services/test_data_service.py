from datetime import date, datetime, time, timedelta
from random import Random

from dateutil.relativedelta import relativedelta

from utils.constants import TransactionType, AccountName, DEFAULT_BILLING_DAY


CATEGORY_DESCRIPTIONS = {
    "Продукти": ["АТБ", "Сільпо", "Овочі", "Молоко", "Хліб"],
    "Кафе та ресторани": ["Кава", "Обід", "Піца", "Суші", "Кафе"],
    "Здоровʼя": ["Аптека", "Вітаміни", "Ліки", "Консультація", "Аналізи"],
    "Спорт": ["Тренування", "Абонемент", "Спортзал", "Басейн", "Фітнес"],
    "Транспорт": ["Таксі", "Метро", "Автобус", "Пальне", "Паркінг"],
    "Будинок": ["Побутова хімія", "Комунальні", "Інтернет", "Лампочки", "Декор"],
    "Догляд": ["Косметика", "Стрижка", "Шампунь", "Догляд", "Перукарня"],
    "Шопінг": ["Одяг", "Взуття", "Покупки", "Аксесуари", "Rozetka"],
    "Відпочинок": ["Кіно", "Прогулянка", "Квитки", "Парк", "Розваги"],
    "Домашні улюбленці": ["Корм", "Ветеринар", "Іграшка", "Наповнювач", "Зоомагазин"],
    "Подарунки": ["Подарунок", "Квіти", "Листівка", "Сувенір", "Свято"],
    "Інше": ["Різне", "Дрібниці", "Послуги", "Покупка", "Інше"],
}

SKIPPED_EXPENSE_CATEGORIES = {
    "Домашні улюбленці",
    "Відпочинок",
    "Інше",
}


async def seed_test_data(db, user_id: int, username: str | None = None) -> dict:
    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    rng = Random(user_id)

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO Users (user_id, username, billing_day)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id)
                DO UPDATE SET username = EXCLUDED.username, billing_day = EXCLUDED.billing_day
                """,
                user_id, username, DEFAULT_BILLING_DAY
            )

            await conn.execute("DELETE FROM Transactions WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM BudgetLimits WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM Accounts WHERE user_id = $1", user_id)

            account_id = await conn.fetchval(
                """
                INSERT INTO Accounts (user_id, name, balance)
                VALUES ($1, $2, 0)
                RETURNING account_id
                """,
                user_id, AccountName.CASH.value
            )

            expense_categories = await conn.fetch(
                """
                SELECT category_id, name
                FROM Categories
                WHERE user_id IS NULL
                  AND type = $1
                  AND name <> ALL($2::text[])
                ORDER BY category_id
                """,
                TransactionType.EXPENSE.value,
                list(SKIPPED_EXPENSE_CATEGORIES)
            )

            if not expense_categories:
                raise RuntimeError("У базі немає стандартних категорій витрат.")

            days_range = (end_date - start_date).days
            expense_count = 0

            for category in expense_categories:
                category_name = category["name"]
                descriptions = CATEGORY_DESCRIPTIONS.get(category_name, ["Тестова витрата"])

                for index in range(6):
                    amount = rng.randint(50, 400)
                    day = start_date + timedelta(days=rng.randint(0, days_range))
                    seconds = rng.randint(8 * 3600, 22 * 3600)
                    created_date = datetime.combine(day, time.min) + timedelta(seconds=seconds)
                    description = descriptions[index % len(descriptions)]

                    await conn.execute(
                        """
                        INSERT INTO Transactions
                            (user_id, account_id, category_id, amount, transaction_type, raw_text, created_date)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        user_id,
                        account_id,
                        category["category_id"],
                        amount,
                        TransactionType.EXPENSE.value,
                        description,
                        created_date
                    )

                    expense_count += 1

            income_category_id = await conn.fetchval(
                """
                SELECT category_id
                FROM Categories
                WHERE user_id IS NULL
                  AND type = $1
                  AND name IN ('Дохід', 'Зарплата')
                ORDER BY CASE WHEN name = 'Дохід' THEN 0 ELSE 1 END
                LIMIT 1
                """,
                TransactionType.INCOME.value
            )

            if not income_category_id:
                income_category_id = await conn.fetchval(
                    """
                    INSERT INTO Categories (name, type, icon_emoji, is_custom)
                    VALUES ('Дохід', $1, '💰', FALSE)
                    RETURNING category_id
                    """,
                    TransactionType.INCOME.value
                )

            incomes = [
                ("Заощадження", 5000, start_date + timedelta(days=2)),
                ("Аванс", 10000, start_date + timedelta(days=15)),
                ("Зарплата", 15000, end_date),
            ]

            for description, amount, income_day in incomes:
                created_date = datetime.combine(income_day, time(hour=10, minute=0))

                await conn.execute(
                    """
                    INSERT INTO Transactions
                        (user_id, account_id, category_id, amount, transaction_type, raw_text, created_date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    user_id,
                    account_id,
                    income_category_id,
                    amount,
                    TransactionType.INCOME.value,
                    description,
                    created_date
                )

            await conn.execute(
                """
                INSERT INTO BudgetLimits (user_id, category_id, target_amount)
                VALUES ($1, NULL, $2)
                """,
                user_id, 20000
            )

            for category in expense_categories:
                limit_amount = rng.randint(10, 50) * 100

                await conn.execute(
                    """
                    INSERT INTO BudgetLimits (user_id, category_id, target_amount)
                    VALUES ($1, $2, $3)
                    """,
                    user_id,
                    category["category_id"],
                    limit_amount
                )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "expense_count": expense_count,
        "income_count": len(incomes),
        "category_count": len(expense_categories),
    }