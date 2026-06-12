import asyncpg
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from utils.constants import TransactionType, DefaultCategory, AccountName, DEFAULT_BILLING_DAY


class DatabaseRepository:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def check_user_exists(self, user_id: int, username: str):
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT user_id FROM Users WHERE user_id = $1", user_id)
            if not user:
                await conn.execute("INSERT INTO Users (user_id, username) VALUES ($1, $2)", user_id, username)

    async def get_user_billing_day(self, user_id: int) -> int:
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow("SELECT billing_day FROM Users WHERE user_id = $1", user_id)
            return record['billing_day'] if record and record['billing_day'] else DEFAULT_BILLING_DAY

    async def update_user_billing_day(self, user_id: int, billing_day: int):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE Users SET billing_day = $1 WHERE user_id = $2", billing_day, user_id)


    async def get_category_id_by_name(self, name: str, user_id: int) -> int:
        normalized_name = name.replace("’", "'").replace("ʼ", "'").replace("`", "'")
        async with self.pool.acquire() as conn:
            category = await conn.fetchrow(
                """
                SELECT category_id FROM Categories 
                WHERE REPLACE(REPLACE(REPLACE(name, '’', ''''), 'ʼ', ''''), '`', '''') = $1
                AND (user_id IS NULL OR user_id = $2)
                """,
                normalized_name, user_id
            )
            if category:
                return category['category_id']

            other = await conn.fetchrow("SELECT category_id FROM Categories WHERE name = $1 AND user_id IS NULL",
                                        DefaultCategory.OTHER.value)
            if other:
                return other['category_id']

            fallback = await conn.fetchrow("SELECT category_id FROM Categories WHERE user_id IS NULL LIMIT 1")
            return fallback['category_id'] if fallback else 1

    async def get_all_user_categories(self, user_id: int, cat_type: str = TransactionType.EXPENSE.value) -> list[dict]:
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT category_id, name, type, icon_emoji, is_custom 
                FROM Categories 
                WHERE (user_id IS NULL OR user_id = $1) AND type = $2
                ORDER BY is_custom ASC, category_id ASC
                """,
                user_id, cat_type
            )
            return [dict(record) for record in records]

    async def count_custom_categories(self, user_id: int) -> int:
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM Categories WHERE user_id = $1 AND is_custom = TRUE",
                                        user_id)
            return count or 0

    async def add_custom_category(self, user_id: int, name: str, icon: str = "🏷️") -> bool:
        async with self.pool.acquire() as conn:
            count = await self.count_custom_categories(user_id)
            if count >= 4:
                return False

            await conn.execute(
                """
                INSERT INTO Categories (user_id, name, type, icon_emoji, is_custom)
                VALUES ($1, $2, $3, $4, TRUE)
                """,
                user_id, name, TransactionType.EXPENSE.value, icon
            )
            return True

    async def delete_custom_category(self, user_id: int, category_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM Categories WHERE category_id = $1 AND user_id = $2 AND is_custom = TRUE",
                               category_id, user_id)

    async def save_transaction(self, user_id: int, amount: float, category_name: str, trans_type: str, raw_text: str,
                               account_name: str = AccountName.CASH.value):
        await self.check_user_exists(user_id, None)

        async with self.pool.acquire() as conn:
            account = await conn.fetchrow("SELECT account_id FROM Accounts WHERE user_id = $1 AND name = $2", user_id,
                                          account_name)
            if not account:
                account_id = await conn.fetchval(
                    "INSERT INTO Accounts (user_id, name, balance) VALUES ($1, $2, 0) RETURNING account_id",
                    user_id, account_name
                )
            else:
                account_id = account['account_id']

            category_id = await self.get_category_id_by_name(category_name, user_id)

            await conn.execute(
                """
                INSERT INTO Transactions (user_id, account_id, category_id, amount, transaction_type, raw_text)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id, account_id, category_id, amount, trans_type, raw_text
            )

    async def update_transaction(self, transaction_id: int, new_amount: float, new_category_name: str,
                                 new_description: str, user_id: int):
        category_id = await self.get_category_id_by_name(new_category_name, user_id)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE Transactions SET amount = $1, category_id = $2, raw_text = $3 WHERE transaction_id = $4 AND user_id = $5",
                new_amount, category_id, new_description, transaction_id, user_id
            )

    async def delete_transaction(self, transaction_id: int, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM Transactions WHERE transaction_id = $1 AND user_id = $2", transaction_id,
                               user_id)


    def get_financial_period(self, billing_day: int) -> tuple[date, date]:
        """Це звичайний метод (не async), бо він не лізе в БД"""
        today = date.today()
        current_month_billing = today.replace(day=billing_day)
        if today >= current_month_billing:
            start_date = current_month_billing
            end_date = start_date + relativedelta(months=1) - timedelta(days=1)
        else:
            start_date = current_month_billing - relativedelta(months=1)
            end_date = current_month_billing - timedelta(days=1)
        return start_date, end_date

    async def get_transactions_by_period(self, user_id: int, start_date: date, end_date: date,
                                         trans_type: str = TransactionType.EXPENSE.value):
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT t.transaction_id as id, t.amount, c.name as category, t.raw_text as description, t.created_date as date
                FROM Transactions t
                JOIN Categories c ON t.category_id = c.category_id
                WHERE t.user_id = $1 
                  AND t.transaction_type = $2
                  AND DATE(t.created_date) >= $3 
                  AND DATE(t.created_date) <= $4
                ORDER BY t.created_date DESC
                """,
                user_id, trans_type, start_date, end_date
            )
            return [dict(record) for record in records]

    async def set_budget_limit(self, user_id: int, target_amount: float, category_id: int = None):
        async with self.pool.acquire() as conn:
            if target_amount == 0:
                if category_id is None:
                    await conn.execute("DELETE FROM BudgetLimits WHERE user_id = $1 AND category_id IS NULL", user_id)
                else:
                    await conn.execute("DELETE FROM BudgetLimits WHERE user_id = $1 AND category_id = $2", user_id,
                                       category_id)
            else:
                await conn.execute(
                    """
                    INSERT INTO BudgetLimits (user_id, category_id, target_amount)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, category_id) 
                    DO UPDATE SET target_amount = EXCLUDED.target_amount
                    """,
                    user_id, category_id, target_amount
                )

    async def get_budget_limit(self, user_id: int, category_id: int = None) -> float | None:
        async with self.pool.acquire() as conn:
            if category_id is None:
                record = await conn.fetchrow(
                    "SELECT target_amount FROM BudgetLimits WHERE user_id = $1 AND category_id IS NULL", user_id)
            else:
                record = await conn.fetchrow(
                    "SELECT target_amount FROM BudgetLimits WHERE user_id = $1 AND category_id = $2", user_id,
                    category_id)
            return float(record['target_amount']) if record else None

    async def get_current_spent(self, user_id: int, category_id: int = None) -> float:
        billing_day = await self.get_user_billing_day(user_id)
        start_date, end_date = self.get_financial_period(billing_day)

        async with self.pool.acquire() as conn:
            if category_id is None:
                query = "SELECT SUM(amount) as total FROM Transactions WHERE user_id = $1 AND transaction_type = $2 AND DATE(created_date) >= $3 AND DATE(created_date) <= $4"
                record = await conn.fetchrow(query, user_id, TransactionType.EXPENSE.value, start_date, end_date)
            else:
                query = "SELECT SUM(amount) as total FROM Transactions WHERE user_id = $1 AND category_id = $2 AND transaction_type = $3 AND DATE(created_date) >= $4 AND DATE(created_date) <= $5"
                record = await conn.fetchrow(query, user_id, category_id, TransactionType.EXPENSE.value, start_date,
                                             end_date)

            return float(record['total']) if record and record['total'] else 0.0

    async def get_all_limits_status(self, user_id: int) -> list[dict]:
        billing_day = await self.get_user_billing_day(user_id)
        start_date, end_date = self.get_financial_period(billing_day)

        results = []
        async with self.pool.acquire() as conn:
            limits = await conn.fetch("SELECT category_id, target_amount FROM BudgetLimits WHERE user_id = $1", user_id)
            if not limits: return []

            for limit_record in limits:
                cat_id = limit_record['category_id']
                limit_amount = float(limit_record['target_amount'])

                if cat_id is None:
                    cat_name = "Загальний бюджет"
                    query = "SELECT SUM(amount) as total FROM Transactions WHERE user_id = $1 AND transaction_type = $2 AND DATE(created_date) >= $3 AND DATE(created_date) <= $4"
                    spent_record = await conn.fetchrow(query, user_id, TransactionType.EXPENSE.value, start_date,
                                                       end_date)
                else:
                    cat_record = await conn.fetchrow("SELECT name FROM Categories WHERE category_id = $1", cat_id)
                    cat_name = cat_record['name'] if cat_record else "Невідома"
                    query = "SELECT SUM(amount) as total FROM Transactions WHERE user_id = $1 AND category_id = $2 AND transaction_type = $3 AND DATE(created_date) >= $4 AND DATE(created_date) <= $5"
                    spent_record = await conn.fetchrow(query, user_id, cat_id, TransactionType.EXPENSE.value,
                                                       start_date, end_date)

                spent_amount = float(spent_record['total']) if spent_record and spent_record['total'] else 0.0
                results.append({"category": cat_name, "limit": limit_amount, "spent": spent_amount})

        results.sort(key=lambda x: 0 if x["category"] == "Загальний бюджет" else 1)
        return results