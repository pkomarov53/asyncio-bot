import asyncio
import sqlite3
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bot token (replace with your actual token)
TOKEN = "7698217701:AAFDiwGxJ1Mrzx10UV8sMn43QxayoUgwA8g"

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()


# Database setup
def init_db():
    conn = sqlite3.connect("bot_database.db")
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
        [KeyboardButton(text="📚 Book Links")],
        [KeyboardButton(text="ℹ️ Useful Information")],
        [KeyboardButton(text="📅 Available Lectures")],
        [KeyboardButton(text="📖 My Lectures")],
        [KeyboardButton(text="🔖 Booked Lectures")]
    ]
)


# Start command handler
@dp.message(Command("start"))
async def start(message: types.Message):
    telegram_id = message.from_user.id
    nickname = message.from_user.username or message.from_user.full_name
    logging.info(f"User {nickname} (ID: {telegram_id}) started the bot.")

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id, nickname) VALUES (?, ?)", (telegram_id, nickname))
    conn.commit()
    conn.close()

    await message.answer(f"Hello, {nickname}! Welcome to the bot.", reply_markup=main_menu)


# Book Links Menu
def get_book_buttons():
    books_folder = "books"
    if not os.path.exists(books_folder):
        os.makedirs(books_folder)

    book_files = [f for f in os.listdir(books_folder) if f.endswith(".txt")]

    keyboard = [[KeyboardButton(text=book.replace(".txt", ""))] for book in book_files]
    keyboard.append([KeyboardButton(text="🔙 Back to Menu")])

    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)


@dp.message(lambda message: message.text == "📚 Book Links")
async def book_links_menu(message: types.Message):
    logging.info(f"User {message.from_user.id} accessed Book Links menu.")
    await message.answer("Choose a book category:", reply_markup=get_book_buttons())


@dp.message()
async def send_book_link(message: types.Message):
    books_folder = "books"
    book_file = os.path.join(books_folder, f"{message.text}.txt")

    if os.path.exists(book_file):
        with open(book_file, "r") as file:
            book_link = file.read().strip()
        logging.info(f"User {message.from_user.id} requested book: {message.text}")
        await message.answer(f"Here is your book link: {book_link}")
    elif message.text == "🔙 Back to Menu":
        logging.info(f"User {message.from_user.id} returned to main menu.")
        await message.answer("Returning to main menu...", reply_markup=main_menu)
    else:
        logging.warning(f"User {message.from_user.id} entered an invalid option: {message.text}")
        await message.answer("Invalid option. Please choose from the menu.")


# Run bot
async def main():
    logging.info("Bot is starting...")
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())