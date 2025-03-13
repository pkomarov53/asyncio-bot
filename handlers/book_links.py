import os
import logging
from aiogram import types, Router
from utils.file_utils import get_file_base_names, get_buttons, read_file_content_async

router = Router()

@router.message(lambda message: message.text == "📚 Ссылки на книги")
async def book_links_menu(message: types.Message) -> None:
    """
    Вывод меню с направлениями книг.
    """
    logging.info(f"User {message.from_user.id} accessed Book Links menu.")
    await message.answer("Выбери направление:", reply_markup=get_buttons("books", (".txt",)))

@router.message(lambda message: message.text in get_file_base_names("books", (".txt",)))
async def send_book_link(message: types.Message) -> None:
    """
    Отправка ссылки на книгу.
    """
    book_file = os.path.join("books", f"{message.text}.txt")
    if os.path.exists(book_file):
        book_link = await read_file_content_async(book_file)
        logging.info(f"User {message.from_user.id} requested book: {message.text}")
        await message.answer(f"Вот ссылка на литературу: https://{book_link}")
