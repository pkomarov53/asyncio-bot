import logging
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Токен вашего бота
TOKEN = "TOKEN"

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Настройки клавиатуры
main_menu = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [KeyboardButton(text="📚 Ссылки на книги")],
        [KeyboardButton(text="ℹ️ Полезная информация")],
        [KeyboardButton(text="📅 Доступные лекции")],
        [KeyboardButton(text="📖 Мои лекции")]
    ]
)