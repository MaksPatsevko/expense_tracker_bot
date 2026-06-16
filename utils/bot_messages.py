from typing import Any

from aiogram.types import Message

from keyboards.reply import main_menu_keyboard


async def answer_with_main_menu(message: Message, text: str, **kwargs: Any) -> Message:
    return await message.bot.send_message(
        chat_id=message.chat.id,
        text=text,
        reply_markup=main_menu_keyboard(),
        reply_parameters=None,
        reply_to_message_id=None,
        **kwargs
    )
