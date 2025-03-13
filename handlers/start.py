import logging
import aiosqlite
from aiogram import types, Router
from aiogram.filters import Command
from config import TOKEN
from utils.file_utils import get_buttons
from database.db import init_db

router = Router()

@router.message(Command("start"))
async def start(message: types.Message) -> None:
    """
    Команда /start – регистрация пользователя в БД и вывод главного меню.
    """
    telegram_id = message.from_user.id
    nickname = message.from_user.username or message.from_user.full_name
    logging.info(f"User @{nickname} (ID: {telegram_id}) started the bot.")
    async with aiosqlite.connect("database/bot_database.database") as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, nickname) VALUES (?, ?)",
            (telegram_id, nickname)
        )
        await conn.commit()
    # Здесь можно импортировать или создавать главное меню из отдельного модуля
    await message.answer(f"Привет, @{nickname}! Добро пожаловать в бот контент-отдела!")
