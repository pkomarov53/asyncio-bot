import asyncio
import sqlite3
import os
import logging
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import Command

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bot token (replace with your actual token)
TOKEN = ""

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

dp.include_router(router)

# Database setup
def init_db():
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect("db/bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            nickname TEXT
        )
    """)
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

# Keyboard setup
main_menu = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [KeyboardButton(text="📚 Ссылки на книги")],
        [KeyboardButton(text="ℹ️ Полезная информация")],
        [KeyboardButton(text="📅 Доступные лекции")],
        [KeyboardButton(text="📖 Мои лекции")],
        [KeyboardButton(text="🔖 Забронированные лекции")]
    ]
)

# Start command handler
@router.message(Command("start"))
async def start(message: types.Message):
    telegram_id = message.from_user.id
    nickname = message.from_user.username or message.from_user.full_name
    logging.info(f"User @{nickname} (ID: {telegram_id}) started the bot.")

    conn = sqlite3.connect("db/bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id, nickname) VALUES (?, ?)", (telegram_id, nickname))
    conn.commit()
    conn.close()

    await message.answer(f"Привет, @{nickname}! Добро пожаловать в бот контент-отдела!", reply_markup=main_menu)

# Book Links Menu
def get_book_buttons():
    books_folder = "books"
    os.makedirs(books_folder, exist_ok=True)

    book_files = [f for f in os.listdir(books_folder) if f.endswith(".txt")]
    keyboard = [[KeyboardButton(text=book.replace(".txt", ""))] for book in book_files]
    keyboard.append([KeyboardButton(text="🔙 Возврат в меню")])

    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)

@router.message(lambda message: message.text == "📚 Ссылки на книги")
async def book_links_menu(message: types.Message):
    logging.info(f"User {message.from_user.id} accessed Book Links menu.")
    await message.answer("Выбери направление:", reply_markup=get_book_buttons())

@router.message(lambda message: message.text in [f.replace(".txt", "") for f in os.listdir("books") if f.endswith(".txt")])
async def send_book_link(message: types.Message):
    books_folder = "books"
    book_file = os.path.join(books_folder, f"{message.text}.txt")

    if os.path.exists(book_file):
        with open(book_file, "r") as file:
            book_link = file.read().strip()
        logging.info(f"User {message.from_user.id} requested book: {message.text}")
        await message.answer(f"Вот ссылка на литературу: {book_link}")

# Useful Information Menu
def get_info_buttons():
    info_folder = "useful_info"
    os.makedirs(info_folder, exist_ok=True)

    info_files = [f for f in os.listdir(info_folder) if f.endswith(".txt") or f.endswith(".pdf")]
    keyboard = [[KeyboardButton(text=file.replace(".txt", "").replace(".pdf", ""))] for file in info_files]
    keyboard.append([KeyboardButton(text="🔙 Возврат в меню")])

    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)

@router.message(lambda message: message.text == "ℹ️ Полезная информация")
async def useful_info_menu(message: types.Message):
    logging.info(f"User {message.from_user.id} accessed Useful Information menu.")
    await message.answer("Нажми на кнопку, чтобы получить полезную информацию:", reply_markup=get_info_buttons())

@router.message(lambda message: message.text in [f.replace(".txt", "").replace(".pdf", "") for f in os.listdir("useful_info") if f.endswith(".txt") or f.endswith(".pdf")])
async def send_useful_info(message: types.Message):
    info_folder = "useful_info"
    txt_file = os.path.join(info_folder, f"{message.text}.txt")
    pdf_file = os.path.join(info_folder, f"{message.text}.pdf")

    if os.path.exists(txt_file):
        with open(txt_file, "r") as file:
            info_text = file.read().strip()
        logging.info(f"User {message.from_user.id} requested info: {message.text}")
        await message.answer(info_text)
    elif os.path.exists(pdf_file):
        logging.info(f"User {message.from_user.id} requested PDF: {message.text}")
        await message.answer_document(FSInputFile(pdf_file))

@router.message(lambda message: message.text == "🔙 Возврат в меню")
async def return_to_menu(message: types.Message):
    logging.info(f"User {message.from_user.id} returned to main menu.")
    await message.answer("Возвращаюсь в главное меню...", reply_markup=main_menu)

# Run bot
async def main():
    logging.info("Bot is starting...")
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
