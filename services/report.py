import logging
from datetime import date
from typing import Tuple
from pathlib import Path

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from services.db import DatabaseRepository
from keyboards.inline import get_expense_categories_keyboard
from utils.chart import generate_expense_pie_chart, generate_daily_dynamics_chart
from utils.constants import TransactionType, Emoji

# Налаштовуємо логер
logger = logging.getLogger(__name__)


async def build_period_report(db: DatabaseRepository, user_id: int, start: date, end: date) -> Tuple[str, InlineKeyboardMarkup | None, list[FSInputFile]]:
    try:
        expenses = await db.get_transactions_by_period(user_id, start, end, TransactionType.EXPENSE.value)
        incomes = await db.get_transactions_by_period(user_id, start, end, TransactionType.INCOME.value)

        total_expense = sum(float(e["amount"]) for e in expenses)
        total_income = sum(float(i["amount"]) for i in incomes)
        balance = total_income - total_expense

        text = f"📊 Дані з {start.strftime('%d.%m.%Y')} по {end.strftime('%d.%m.%Y')}:\n\n"
        text += f"{Emoji.INCOME_ICON.value} Прибуток: `{total_income:.2f} грн`\n" if incomes else f"{Emoji.INCOME_ICON.value} Прибуток: `0.00 грн`\n"
        text += f"{Emoji.EXPENSE_ICON.value} Витрати: `{total_expense:.2f} грн`\n" if expenses else f"{Emoji.EXPENSE_ICON.value} Витрати: `0.00 грн`\n"
        text += f"🧾 Баланс: `{balance:.2f} грн`\n"

        reply_markup = None
        chart_files = [] # ТЕПЕР ЦЕ СПИСОК (Масив) КАРТИНОК

        if incomes:
            text += "\n💰 **Деталі прибутків:**\n"
            for inc in incomes:
                comment = inc.get('description', '').strip()
                comment_part = f" ({comment})" if comment else ""
                text += f"• `{float(inc['amount']):.2f} грн`{comment_part}\n"

        keyboard = []

        if expenses:
            text += "\n📌 **Витрати за категоріями:**"
            category_sums = {}
            for exp in expenses:
                cat = exp["category"]
                category_sums[cat] = category_sums.get(cat, 0) + float(exp["amount"])

            categories_keyboard = get_expense_categories_keyboard(category_sums)
            keyboard.extend(categories_keyboard.inline_keyboard)

            # 1. Побудова Кругової діаграми (Pie Chart) - робимо завжди
            pie_chart_path = Path(f"pie_{user_id}.png")
            generate_expense_pie_chart(category_sums, start, end, file_path=str(pie_chart_path))
            chart_files.append(FSInputFile(path=str(pie_chart_path), filename="pie_chart.png"))

            # 2. Побудова Стовпчастої діаграми динаміки (ТІЛЬКИ якщо період > 1 дня)
            delta_days = (end - start).days
            if delta_days > 0: # Тобто це мінімум 2 дні
                dyn_chart_path = Path(f"dyn_{user_id}.png")
                # Передаємо expenses у генератор
                generate_daily_dynamics_chart(expenses, start, end, file_path=str(dyn_chart_path))
                chart_files.append(FSInputFile(path=str(dyn_chart_path), filename="dynamics_chart.png"))

        else:
            text += "\n📌 Витрати відсутні за цей період."

        keyboard.append([InlineKeyboardButton(text="🔄 Змінити період", callback_data="change_period")])
        keyboard.append([InlineKeyboardButton(text="📥 Експортувати у CSV", callback_data=f"export_csv:{start}:{end}")])
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        return text, reply_markup, chart_files # ПОВЕРТАЄМО СПИСОК

    except Exception as e:
        logger.error("Помилка при генерації звіту (User %s): %s", user_id, e)
        return "⚠️ Виникла помилка при формуванні звіту.", None, []