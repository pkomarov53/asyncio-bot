import os
import aiofiles
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_file_base_names(folder: str, extensions: tuple) -> list:
    """
    Возвращает список имён файлов (без расширений) из указанной папки.
    """
    os.makedirs(folder, exist_ok=True)
    return [os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith(extensions)]

def get_buttons(folder: str, extensions: tuple) -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру с кнопками на основе имён файлов из указанной папки.
    """
    base_names = get_file_base_names(folder, extensions)
    keyboard = [[KeyboardButton(text=name)] for name in base_names]
    keyboard.append([KeyboardButton(text="🔙 Возврат в меню")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)

async def read_file_content_async(file_path: str, encoding: str = "utf-8") -> str:
    """
    Асинхронно читает содержимое файла.
    """
    async with aiofiles.open(file_path, "r", encoding=encoding) as file:
        content = await file.read()
    return content.strip()

async def read_lines_async(file_path: str, encoding: str = "utf-8") -> list:
    """
    Асинхронно читает строки из файла, возвращая непустые строки.
    """
    content = await read_file_content_async(file_path, encoding)
    return [line.strip() for line in content.splitlines() if line.strip()]
