import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
from utils.constants import TransactionType, DefaultCategory

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def parse_transaction_text_ai(text: str, user_categories_list: list[str]) -> dict | None:
    categories_string = ", ".join(user_categories_list)

    prompt = f"""
    Ти — фінансовий аналізатор у системі PFM.
    Розпізнай фінансову операцію з тексту користувача: "{text}"

    Правила:
    1. Знайти суму (amount) як число типу float. Якщо суми немає - amount має бути null.
    2. Визначити категорію (category) ТІЛЬКИ з цього списку: [{categories_string}].
       Якщо не підходить жодна - "{DefaultCategory.OTHER.value}".
    3. Визначити тип (type): "{TransactionType.EXPENSE.value}" або "{TransactionType.INCOME.value}".
    4. Сформувати description - короткий опис операції БЕЗ суми, валюти та зайвих слів біля суми.
       Наприклад:
       - "Кава 65" -> description: "Кава"
       - "Купив продукти в Сільпо на 1250.50" -> description: "Купив продукти в Сільпо"
       - "Таксі 200 грн" -> description: "Таксі"
       - "Аванс 15000" -> description: "Аванс"

    Поверни результат виключно у форматі JSON з полями:
    amount, category, type, description.
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a helpful financial assistant designed to output JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

        json_text = response.choices[0].message.content
        data = json.loads(json_text)

        if not data.get("amount"):
            return None

        if not data.get("category"):
            data["category"] = DefaultCategory.OTHER.value

        description = str(data.get("description") or "").strip()
        if not description:
            description = text

        data["description"] = description
        return data

    except Exception as e:
        print(f"Помилка OpenAI API: {e}")
        return None