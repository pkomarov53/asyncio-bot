import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TOKEN
from database.db import init_db
from handlers import start, book_links, useful_info, lectures, my_lectures, return_to_menu

async def main() -> None:
    logging.info("Bot is starting...")
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Регистрация роутеров из разных модулей
    dp.include_router(start.router)
    dp.include_router(book_links.router)
    dp.include_router(useful_info.router)
    dp.include_router(lectures.router)
    dp.include_router(my_lectures.router)
    dp.include_router(return_to_menu.router)

    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
