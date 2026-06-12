import aiohttp
from aiohttp import web
import os
import logging

from utils.constants import TransactionType, DefaultCategory, AccountName
from services.transaction_service import process_and_save_transaction

logger = logging.getLogger(__name__)

# Словник: MCC код Monobank -> Твоя категорія в БД (яка має точно збігатися з таблицею Categories)
MCC_MAPPING = {
    # --- Продукти ---
    5411: "Продукти",       # Супермаркети (АТБ, Сільпо, Ашан, Novus)
    5499: "Продукти",       # Продовольчі магазини, кіоски
    5422: "Продукти",       # М'ясні магазини
    5462: "Продукти",       # Булочні, пекарні
    5441: "Продукти",       # Кондитерські

    # --- Кафе та ресторани ---
    5812: "Кафе та ресторани", # Ресторани
    5814: "Кафе та ресторани", # Фаст-фуд (McDonalds, KFC, шаурма)
    5813: "Кафе та ресторани", # Бари, паби, нічні клуби
    5811: "Кафе та ресторани", # Кейтеринг (доставка їжі)

    # --- Транспорт ---
    4121: "Транспорт",      # Таксі (Uklon, Uber, Bolt)
    4111: "Транспорт",      # Місцевий пасажирський транспорт (метро, тролейбуси)
    4131: "Транспорт",      # Автобусні лінії
    4112: "Транспорт",      # Пасажирські залізничні перевезення (Укрзалізниця)
    5541: "Транспорт",      # АЗС (заправки)
    5542: "Транспорт",      # Автоматизовані бензоколонки
    7523: "Транспорт",      # Паркінги, гаражі
    4789: "Транспорт",      # Інші послуги пасажирських перевезень (прокат самокатів)

    # --- Здоровʼя ---
    5122: "Здоровʼя",       # Аптеки
    5912: "Здоровʼя",       # Аптеки (роздріб)
    8011: "Здоровʼя",       # Лікарі (клініки)
    8021: "Здоровʼя",       # Стоматологія
    8099: "Здоровʼя",       # Медичні послуги та обладнання

    # --- Розваги ---
    7832: "Розваги",        # Кінотеатри
    7999: "Розваги",        # Інші розваги (боулінг, картинг тощо)
    7922: "Розваги",        # Театри, квитки на концерти
    4899: "Розваги",        # Кабельні та інші платні телевізійні послуги (Megogo, Netflix)
    5815: "Розваги",        # Відеоігри, цифрові товари (Steam, PlayStation)

    # --- Догляд ---
    5977: "Догляд",         # Магазини косметики (Eva, Watsons, Prostor)
    7230: "Догляд",         # Салони краси, барбершопи
    7299: "Догляд",         # Інші послуги догляду за собою (масаж, спа)

    # --- Шопінг ---
    5691: "Шопінг",         # Магазини чоловічого та жіночого одягу
    5621: "Шопінг",         # Жіночий одяг
    5661: "Шопінг",         # Дитячий одяг
    5651: "Шопінг",         # Взуття
    5311: "Шопінг",         # Універмаги (Rozetka не продукти, Епіцентр)
    5999: "Шопінг",         # Різні товари (Аврора тощо)

    # --- Будинок ---
    5200: "Будинок",        # Товари для дому (Епіцентр, Jysk)
    5712: "Будинок",        # Обладнання, меблі
    4900: "Будинок",        # Комунальні послуги (електрика, газ, вода)
    4814: "Будинок",        # Телекомунікаційні послуги (Інтернет, поповнення мобільного)

    # --- Спорт ---
    5941: "Спорт",          # Спортивні товари
    7997: "Спорт",          # Спортивні клуби, фітнес-центри (SportLife)

    # --- Домашні улюбленці ---
    5995: "Домашні улюбленці", # Зоомагазини (MasterZoo)
    742: "Домашні улюбленці", # Ветеринарні послуги

    # --- Подарунки ---
    5947: "Подарунки",      # Магазини подарунків та сувенірів
    5992: "Подарунки",      # Флористика (Квіти)
}


async def setup_monobank_webhook(mono_token: str, user_id: int) -> bool:
    """
    Автоматично реєструє вебхук у Монобанку для конкретного користувача.
    """
    base_url = os.getenv("WEBHOOK_BASE_URL")
    user_webhook_url = f"{base_url}/mono/{user_id}"

    headers = {
        "X-Token": mono_token,
        "Content-Type": "application/json"
    }
    payload = {
        "webHookUrl": user_webhook_url
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.monobank.ua/personal/webhook", headers=headers, json=payload) as response:
            if response.status == 200:
                logger.info("Webhook для юзера %s успішно встановлено!", user_id)
                return True
            else:
                text = await response.text()
                logger.error("Помилка встановлення Webhook для юзера %s: %s", user_id, text)
                return False


async def handle_mono_webhook(request):
    """
    Обробляє POST-запити від Monobank (оплати, перекази).
    """
    try:
        user_id_str = request.match_info.get('user_id')
        if not user_id_str:
            logger.warning("Webhook Error: Відсутній user_id у посиланні")
            return web.Response(text="Bad Request", status=400)

        user_id = int(user_id_str)
        data = await request.json()

        if data.get("type") == "webhook_test":
            return web.Response(text="OK", status=200)

        if data.get("type") == "StatementItem":
            statement = data["data"]["statementItem"]

            amount_kopecks = statement["amount"]

            # Ігноруємо поповнення картки
            if amount_kopecks >= 0:
                return web.Response(text="OK", status=200)

            amount = abs(amount_kopecks) / 100.0
            description = statement.get("description", "Без опису")
            mcc = statement.get("mcc", 0)

            # Визначаємо категорію (через константу)
            category_name = MCC_MAPPING.get(mcc, DefaultCategory.OTHER.value)

            db = request.app["db"]
            bot = request.app["bot"]

            # Переконуємось, що користувач є в базі
            await db.check_user_exists(user_id, "mono_user")

            final_description = f"[Mono] {description}"

            # ВИКЛИК СЕРВІСУ! (Він сам зберігає, перевіряє ліміти і генерує текст)
            final_message = await process_and_save_transaction(
                db=db,
                user_id=user_id,
                amount=amount,
                category_name=category_name,
                trans_type=TransactionType.EXPENSE.value,
                description=final_description,
                source_name="Monobank",
                account_name=AccountName.MONOBANK.value
            )

            # Відправляємо готове сповіщення
            await bot.send_message(
                chat_id=user_id,
                text=final_message,
                parse_mode="Markdown"
            )

        return web.Response(text="OK", status=200)

    except Exception as e:
        logger.error("Помилка обробки Webhook: %s", e)
        return web.Response(text="Error", status=500)