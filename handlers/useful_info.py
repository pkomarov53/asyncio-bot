import os
import logging
from aiogram import types, Router
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from utils.file_utils import get_file_base_names, get_buttons, read_file_content_async

router = Router()

@router.message(lambda message: message.text == "ℹ️ Полезная информация")
async def useful_info_menu(message: types.Message) -> None:
    """
    Вывод меню с полезной информацией.
    """
    logging.info(f"User {message.from_user.id} accessed Useful Information menu.")
    await message.answer(
        "Нажми на кнопку, чтобы получить полезную информацию:",
        reply_markup=get_buttons("useful_info", (".txt", ".pdf"))
    )

@router.message(lambda message: message.text in get_file_base_names("useful_info", (".txt", ".pdf")))
async def send_useful_info(message: types.Message) -> None:
    """
    Отправка полезной информации: текст или PDF.
    """
    info_folder = "useful_info"
    txt_file = os.path.join(info_folder, f"{message.text}.txt")
    pdf_file = os.path.join(info_folder, f"{message.text}.pdf")
    if os.path.exists(txt_file):
        info_text = await read_file_content_async(txt_file)
        logging.info(f"User {message.from_user.id} requested info: {message.text}")
        await message.answer(info_text)
    elif os.path.exists(pdf_file):
        logging.info(f"User {message.from_user.id} requested PDF: {message.text}")
        await message.answer_document(FSInputFile(pdf_file))
