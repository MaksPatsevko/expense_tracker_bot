import csv
import os
from datetime import date
from services.db import DatabaseRepository
from utils.constants import TransactionType


async def generate_csv_report(db: DatabaseRepository, user_id: int, start_date: date, end_date: date) -> str | None:
    """
    Генерує CSV-файл з транзакціями, згрупованими за категоріями, та лімітами.
    """
    file_name = f"finance_report_{user_id}_{start_date}_to_{end_date}.csv"

    try:
        # 1. Отримуємо дані з БД
        expenses = await db.get_transactions_by_period(user_id, start_date, end_date, TransactionType.EXPENSE.value)
        incomes = await db.get_transactions_by_period(user_id, start_date, end_date, TransactionType.INCOME.value)
        limits_status = await db.get_all_limits_status(user_id)

        # Відкриваємо файл (utf-8-sig гарантує правильне читання кирилиці в Excel)
        with open(file_name, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file, delimiter=';')

            writer.writerow(['ФІНАНСОВИЙ ЗВІТ'])
            writer.writerow(['Період:', f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"])
            writer.writerow([])

            # --- БЛОК 1: ЗВЕДЕНА СТАТИСТИКА (ГРУПУВАННЯ) ---
            writer.writerow(['--- СУМИ ЗА КАТЕГОРІЯМИ ---'])
            writer.writerow(['Категорія', 'Тип', 'Загальна сума (грн)'])

            # Групуємо прибутки
            income_sums = {}
            for i in incomes:
                cat = i['category']
                income_sums[cat] = income_sums.get(cat, 0.0) + float(i['amount'])

            for cat, total in income_sums.items():
                writer.writerow([cat, 'Дохід', f"{total:.2f}"])

            # Групуємо витрати
            expense_sums = {}
            for e in expenses:
                cat = e['category']
                expense_sums[cat] = expense_sums.get(cat, 0.0) + float(e['amount'])

            for cat, total in expense_sums.items():
                writer.writerow([cat, 'Витрата', f"{total:.2f}"])

            writer.writerow([])

            # --- БЛОК 2: СТАТУС БЮДЖЕТІВ ---
            writer.writerow(['--- СТАТУС БЮДЖЕТНИХ ЛІМІТІВ ---'])
            writer.writerow(['Категорія', 'Ліміт (грн)', 'Витрачено (грн)', 'Залишок (грн)', 'Використано (%)'])

            if limits_status:
                for lim in limits_status:
                    limit_amt = float(lim['limit'])
                    spent_amt = float(lim['spent'])
                    remains = limit_amt - spent_amt
                    percent = (spent_amt / limit_amt * 100) if limit_amt > 0 else 0

                    writer.writerow([
                        lim['category'],
                        f"{limit_amt:.2f}",
                        f"{spent_amt:.2f}",
                        f"{remains:.2f}",
                        f"{percent:.1f}%"
                    ])
            else:
                writer.writerow(['Ліміти не встановлено', '', '', '', ''])

            writer.writerow([])

            # --- БЛОК 3: ДЕТАЛІЗАЦІЯ ОПЕРАЦІЙ ---
            writer.writerow(['--- ІСТОРІЯ ВСІХ ТРАНЗАКЦІЙ ---'])
            writer.writerow(['Дата', 'Час', 'Тип', 'Сума (грн)', 'Категорія', 'Опис'])

            all_transactions = expenses + incomes
            # Сортуємо по даті (найновіші зверху)
            all_transactions.sort(key=lambda x: x['date'], reverse=True)

            for t in all_transactions:
                t_type = "Дохід" if t in incomes else "Витрата"

                # Розділяємо дату і час для зручності в Excel (вирішує проблему з #####)
                date_str = t['date'].strftime('%d.%m.%Y')
                time_str = t['date'].strftime('%H:%M')

                writer.writerow([
                    date_str,
                    time_str,
                    t_type,
                    f"{float(t['amount']):.2f}",
                    t['category'],
                    t['description']
                ])

        return file_name

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Помилка генерації CSV: {e}")
        return None