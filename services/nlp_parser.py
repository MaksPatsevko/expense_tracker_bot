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
    1. Знайти суму (amount) як число типу float (наприклад 150.0). Якщо суми немає - amount має бути null.
    2. Визначити категорію (category) ТІЛЬКИ з цього списку: [{categories_string}]. Якщо не підходить жодна - "{DefaultCategory.OTHER.value}".
    3. Визначити тип (type): "{TransactionType.EXPENSE.value}" (витрата) або "{TransactionType.INCOME.value}" (прибуток/зарплата/перекази).

    Ти ПОВИНЕН повернути результат виключно у форматі JSON.
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

        data['description'] = text
        return data

    except Exception as e:
        print(f"Помилка OpenAI API: {e}")
        return None