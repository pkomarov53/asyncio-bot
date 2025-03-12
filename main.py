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
TOKEN = "7698217701:AAFDiwGxJ1Mrzx10UV8sMn43QxayoUgwA8g"

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lecture TEXT,
            direction TEXT,
            FOREIGN KEY(user_id) REFERENCES users(telegram_id)
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
        await message.answer(f"Вот ссылка на литературу: https://{book_link}")

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
        with open(txt_file, "r", encoding="utf-8") as file:
            info_text = file.read().strip()
        logging.info(f"User {message.from_user.id} requested info: {message.text}")
        await message.answer(info_text)
    elif os.path.exists(pdf_file):
        logging.info(f"User {message.from_user.id} requested PDF: {message.text}")
        await message.answer_document(FSInputFile(pdf_file))

# Available Lectures Menu
def get_lecture_directions():
    lections_folder = "lections"
    os.makedirs(lections_folder, exist_ok=True)

    directions = [f.replace(".txt", "") for f in os.listdir(lections_folder) if f.endswith(".txt")]
    keyboard = [[KeyboardButton(text=direction)] for direction in directions]
    keyboard.append([KeyboardButton(text="🔙 Возврат в меню")])

    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)


@router.message(lambda message: message.text == "📅 Доступные лекции")
async def available_lectures_menu(message: types.Message):
    logging.info(f"User {message.from_user.id} accessed Available Lectures menu.")
    await message.answer("Выбери направление лекций:", reply_markup=get_lecture_directions())


@router.message(
    lambda message: message.text in [f.replace(".txt", "") for f in os.listdir("lections") if f.endswith(".txt")])
async def show_lectures(message: types.Message):
    direction = message.text
    lections_folder = "lections"
    lection_file = os.path.join(lections_folder, f"{direction}.txt")

    if os.path.exists(lection_file):
        with open(lection_file, "r", encoding="utf-8") as file:
            lectures = [line.strip() for line in file.readlines() if line.strip()]

        conn = sqlite3.connect("db/bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT lecture FROM bookings WHERE direction = ?", (direction,))
        booked_lectures = {row[0] for row in cursor.fetchall()}
        conn.close()

        available_lectures = [lecture for lecture in lectures if lecture not in booked_lectures]

        if not available_lectures:
            await message.answer("Нет доступных лекций в этом направлении.")
            return

        lecture_list = "\n".join([f"📌 {i + 1}. {lecture}\n" for i, lecture in enumerate(available_lectures)])

        await message.answer(
            f"📖 *Доступные лекции в направлении* _{direction}_:\n\n{lecture_list}\nВведите номер лекции, чтобы забронировать.",
            parse_mode="Markdown")

        @router.message(lambda msg: msg.text.isdigit())
        async def book_lecture(msg: types.Message):
            lecture_number = int(msg.text)
            if 1 <= lecture_number <= len(available_lectures):
                selected_lecture = available_lectures[lecture_number - 1]
                user_id = msg.from_user.id

                conn = sqlite3.connect("db/bot_database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO bookings (user_id, lecture, direction) VALUES (?, ?, ?)",
                               (user_id, selected_lecture, direction))
                conn.commit()
                conn.close()

                logging.info(f"User {user_id} booked lecture: {selected_lecture} ({direction})")
                await msg.answer(f"✅ Лекция *'{selected_lecture}'* успешно забронирована!", parse_mode="Markdown")
            else:
                await msg.answer("⚠️ Некорректный номер лекции. Попробуйте снова.")
    else:
        await message.answer("❌ Ошибка: направление не найдено.")

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
