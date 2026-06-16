import matplotlib.pyplot as plt
from datetime import date
from matplotlib import rcParams
import numpy as np

# --- ГЛОБАЛЬНІ НАЛАШТУВАННЯ ДИЗАЙНУ ---
# Використовуємо сучасний шрифт та м'який фон
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Tahoma']
rcParams['text.color'] = '#2C3E50'
rcParams['axes.labelcolor'] = '#2C3E50'
rcParams['xtick.color'] = '#34495E'
rcParams['ytick.color'] = '#34495E'

MODERN_COLORS = [
    '#FF9F43', '#00CFE8', '#28C76F', '#EA5455', '#7367F0',
    '#FFC107', '#1ABC9C', '#9B59B6', '#34495E', '#F39C12'
]

UKR_MONTHS = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}


def generate_expense_pie_chart(category_sums: dict, start_date: date, end_date: date, file_path="chart.png"):
    """
    Малює сучасну діаграму-кільце (Donut Chart) для категорій.
    """
    if not category_sums:
        return None

    plt.clf()
    plt.close('all')

    labels = list(category_sums.keys())
    sizes = list(category_sums.values())
    total_spent = sum(sizes)

    # Робимо квадратний графік з м'яким сірим фоном
    fig, ax = plt.subplots(figsize=(7, 7), facecolor='#F8F9FA')
    ax.set_facecolor('#F8F9FA')

    # Малюємо кільце: параметр wedgeprops=dict(width=0.35) робить дірку всередині
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct='%1.1f%%',
        startangle=90,
        colors=MODERN_COLORS[:len(labels)],
        pctdistance=0.82,  # Відсуваємо відсотки ближче до краю
        textprops=dict(fontsize=11, fontweight='bold', color='#2C3E50'),
        wedgeprops=dict(width=0.4, edgecolor='#F8F9FA', linewidth=3)  # Білі рамки між шматками
    )

    ax.axis('equal')

    # МАГІЯ: Додаємо текст у центр кільця
    ax.text(0, 0.1, "Всього витрачено", ha='center', va='center', fontsize=12, color='#7F8C8D')
    ax.text(0, -0.1, f"{total_spent:g} ₴", ha='center', va='center', fontsize=22, fontweight='bold', color='#2C3E50')

    title = f"Статистика витрат за категоріями\n({start_date.day} {UKR_MONTHS[start_date.month]} - {end_date.day} {UKR_MONTHS[end_date.month]})"
    plt.title(title, fontsize=15, pad=20, fontweight='bold')

    plt.tight_layout()
    plt.savefig(file_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

    return file_path


def generate_daily_dynamics_chart(expenses: list[dict], start_date: date, end_date: date,
                                  file_path="dynamics_chart.png"):

    from collections import defaultdict
    if not expenses:
        return None

    plt.clf()
    plt.close('all')

    daily_sums = defaultdict(float)

    for exp in expenses:
        exp_date = exp['date']

        if hasattr(exp_date, "date"):
            exp_date = exp_date.date()

        daily_sums[exp_date] += float(exp['amount'])

    sorted_dates = sorted(daily_sums.keys())

    ukr_weekdays = {
        0: "пн",
        1: "вт",
        2: "ср",
        3: "чт",
        4: "пт",
        5: "сб",
        6: "нд",
    }

    labels = [
        f"{day.strftime('%d.%m')}({ukr_weekdays[day.weekday()]})"
        for day in sorted_dates
    ]

    sums = [daily_sums[day] for day in sorted_dates]

    fig_width = max(8.0, len(labels) * 0.7)
    fig, ax = plt.subplots(figsize=(fig_width, 5.5), facecolor='#F8F9FA')
    ax.set_facecolor('#F8F9FA')

    ax.grid(axis='y', linestyle='--', alpha=0.6, color='#BDC3C7', zorder=0)

    bars = ax.bar(labels, sums, color='#00CFE8', width=0.5, edgecolor='white', linewidth=1.5, zorder=3, alpha=0.9)

    for bar in bars:
        yval = bar.get_height()
        if yval > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                yval + (max(sums) * 0.03),
                f"{yval:g}",
                ha='center',
                va='bottom',
                fontsize=10,
                fontweight='bold',
                color='#2C3E50'
            )

    ax.set_title("Статистика витрат по днях", fontsize=15, pad=20, fontweight='bold')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#BDC3C7')
    ax.set_yticks([])

    font_size = 10 if len(labels) <= 10 else 8
    rotation = 0 if len(labels) <= 10 else 30
    ha = 'center' if len(labels) <= 10 else 'right'

    plt.xticks(rotation=rotation, ha=ha, fontsize=font_size)
    ax.set_ylim(0, max(sums) * 1.2)

    plt.tight_layout()
    plt.savefig(file_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close('all')

    return file_path

def generate_limits_bar_chart(limits_data: list[dict], period_text: str, file_path="limits_chart.png"):
    """
    Малює горизонтальний графік лімітів у єдиному стилі.
    """
    if not limits_data:
        return None

    plt.clf()
    plt.close('all')

    categories = [item['category'] for item in limits_data][::-1]
    limits = [float(item['limit']) for item in limits_data][::-1]
    spents = [float(item['spent']) for item in limits_data][::-1]

    fig_height = max(4.0, len(categories) * 0.8)
    fig, ax = plt.subplots(figsize=(8, fig_height), facecolor='#F8F9FA')
    ax.set_facecolor('#F8F9FA')

    # Фоновий ліміт
    ax.barh(categories, limits, color='#E2E8F0', height=0.5, label='Ліміт', edgecolor='white', linewidth=1)

    colors = []
    for s, l in zip(spents, limits):
        if l == 0:
            colors.append('#28C76F')
        elif s >= l:
            colors.append('#EA5455')
        elif s >= l * 0.8:
            colors.append('#FF9F43')
        else:
            colors.append('#28C76F')

        # Витрати
    ax.barh(categories, spents, color=colors, height=0.35, label='Витрачено', zorder=3)

    for i, (spent, limit) in enumerate(zip(spents, limits)):
        percentage = (spent / limit * 100) if limit > 0 else 0
        text = f"{spent:g} / {limit:g} ({percentage:.0f}%)"
        max_val = max(spent, limit)
        text_x_pos = max_val + (max(limits) * 0.05)
        ax.text(text_x_pos, i, text, va='center', fontsize=11, fontweight='bold', color='#2C3E50')

    ax.set_title(f"Статус бюджетних лімітів\n({period_text})", fontsize=15, pad=15, fontweight='bold')

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_xticks([])
    ax.tick_params(axis='y', length=0, labelsize=11)
    ax.set_xlim(0, max(max(limits), max(spents)) * 1.35)

    plt.tight_layout()
    plt.savefig(file_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close('all')

    return file_path