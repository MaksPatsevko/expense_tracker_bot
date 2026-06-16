from enum import Enum

class TransactionType(str, Enum):
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"

class DefaultCategory(str, Enum):
    OTHER = "Інше"
    SALARY = "Дохід"

class AccountName(str, Enum):
    CASH = "Готівка 💵"
    MONOBANK = "Monobank 🐈"

class Emoji(str, Enum):
    SUCCESS = "✅"
    WARNING = "⚠️"
    CRITICAL = "🚨"
    INFO = "ℹ️"
    EXPENSE_ICON = "💸"
    INCOME_ICON = "💰"

MAX_CUSTOM_CATEGORIES = 4
DEFAULT_BILLING_DAY = 1