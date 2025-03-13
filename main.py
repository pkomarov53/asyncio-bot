import asyncio
import os
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOKEN = "TOKEN"

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# Определение состояний для бронирования лекций
class BookingState(StatesGroup):
    waiting_for_direction = State()
    waiting_for_lecture = State()


async def init_db() -> None:
    """
    Асинхронная инициализация базы данных с созданием необходимых таблиц.
    """
    os.makedirs("db", exist_ok=True)
    async with aiosqlite.connect("db/bot_database.db") as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                nickname TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lecture TEXT,
                direction TEXT,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id)
            )
        """)
        await conn.commit()
    logging.info("Database initialized successfully.")


def get_buttons(folder: str, extensions: tuple) -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру с кнопками, имена которых получены из файлов указанной папки с нужными расширениями.
    """
    os.makedirs(folder, exist_ok=True)
    files = [f for f in os.listdir(folder) if f.endswith(extensions)]
    keyboard = [[KeyboardButton(text=os.path.splitext(f)[0])] for f in files]
    keyboard.append([KeyboardButton(text="🔙 Возврат в меню")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)


def read_file_content(file_path: str, encoding: str = "utf-8") -> str:
    """
    Читает содержимое файла и возвращает его в виде строки.
    """
    with open(file_path, "r", encoding=encoding) as file:
        return file.read().strip()


# Главное меню бота
main_menu = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [KeyboardButton(text="📚 Ссылки на книги")],
        [KeyboardButton(text="ℹ️ Полезная информация")],
        [KeyboardButton(text="📅 Доступные лекции")],
        [KeyboardButton(text="📖 Мои лекции")]
    ]
)


@router.message(Command("start"))
async def start(message: types.Message) -> None:
    """
    Команда /start – регистрация пользователя в базе и вывод главного меню.
    """
    telegram_id = message.from_user.id
    nickname = message.from_user.username or message.from_user.full_name
    logging.info(f"User @{nickname} (ID: {telegram_id}) started the bot.")
    async with aiosqlite.connect("db/bot_database.db") as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, nickname) VALUES (?, ?)",
            (telegram_id, nickname)
        )
        await conn.commit()
    await message.answer(f"Привет, @{nickname}! Добро пожаловать в бот контент-отдела!", reply_markup=main_menu)


@router.message(lambda message: message.text == "📚 Ссылки на книги")
async def book_links_menu(message: types.Message) -> None:
    """
    Вывод меню с направлениями книг.
    """
    logging.info(f"User {message.from_user.id} accessed Book Links menu.")
    await message.answer("Выбери направление:", reply_markup=get_buttons("books", (".txt",)))


@router.message(
    lambda message: message.text in [os.path.splitext(f)[0] for f in os.listdir("books") if f.endswith(".txt")])
async def send_book_link(message: types.Message) -> None:
    """
    Отправка ссылки на книгу, если файл найден.
    """
    book_file = os.path.join("books", f"{message.text}.txt")
    if os.path.exists(book_file):
        book_link = read_file_content(book_file)
        logging.info(f"User {message.from_user.id} requested book: {message.text}")
        await message.answer(f"Вот ссылка на литературу: https://{book_link}")


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


@router.message(lambda message: message.text in [os.path.splitext(f)[0] for f in os.listdir("useful_info") if
                                                 f.endswith(".txt") or f.endswith(".pdf")])
async def send_useful_info(message: types.Message) -> None:
    """
    Отправка полезной информации: текст или PDF документ.
    """
    info_folder = "useful_info"
    txt_file = os.path.join(info_folder, f"{message.text}.txt")
    pdf_file = os.path.join(info_folder, f"{message.text}.pdf")

    if os.path.exists(txt_file):
        info_text = read_file_content(txt_file)
        logging.info(f"User {message.from_user.id} requested info: {message.text}")
        await message.answer(info_text)
    elif os.path.exists(pdf_file):
        logging.info(f"User {message.from_user.id} requested PDF: {message.text}")
        await message.answer_document(FSInputFile(pdf_file))


@router.message(lambda message: message.text == "📅 Доступные лекции")
async def available_lectures_menu(message: types.Message, state: FSMContext) -> None:
    """
    Вывод меню с доступными лекциями по направлению.
    """
    logging.info(f"User {message.from_user.id} accessed Available Lectures menu.")
    await message.answer("Выбери направление лекций:", reply_markup=get_buttons("lections", (".txt",)))
    await state.set_state(BookingState.waiting_for_direction)


@router.message(
    lambda message: message.text in [os.path.splitext(f)[0] for f in os.listdir("lections") if f.endswith(".txt")])
async def show_lectures(message: types.Message, state: FSMContext) -> None:
    """
    Отображение списка лекций для выбранного направления с индикаторами бронирования.
    """
    direction = message.text
    lection_file = os.path.join("lections", f"{direction}.txt")
    logging.info(f"Opening file for direction '{direction}': {lection_file}")

    if os.path.exists(lection_file):
        with open(lection_file, "r", encoding="utf-8") as file:
            lectures = [line.strip() for line in file if line.strip()]

        async with aiosqlite.connect("db/bot_database.db") as conn:
            async with conn.execute("SELECT lecture FROM bookings WHERE direction = ?", (direction,)) as cursor:
                rows = await cursor.fetchall()
                booked_lectures = {row[0] for row in rows}

        await state.update_data(direction=direction)

        lecture_list = ""
        for i, lecture in enumerate(lectures):
            status = "🔴" if lecture in booked_lectures else "🟢"
            lecture_list += f"{status} {i + 1}. {lecture}\n\n"

        await message.answer(
            f"📖 *Доступные лекции в направлении* _{direction}_:\n\n{lecture_list}Введите номер лекции, чтобы забронировать.",
            parse_mode="Markdown"
        )
        await state.set_state(BookingState.waiting_for_lecture)
    else:
        await message.answer(f"❌ Направление '{direction}' не найдено.")


@router.message(lambda msg: msg.text.isdigit())
async def book_lecture(msg: types.Message, state: FSMContext) -> None:
    """
    Обработка бронирования выбранной лекции.
    """
    user_data = await state.get_data()
    direction = user_data.get('direction')
    if not direction:
        await msg.answer("❌ Ошибка: не выбрано направление для бронирования.")
        return

    lection_file = os.path.join("lections", f"{direction}.txt")
    if not os.path.exists(lection_file):
        await msg.answer("❌ Ошибка: направление не найдено.")
        return

    with open(lection_file, "r", encoding="utf-8") as file:
        lectures = [line.strip() for line in file if line.strip()]

    lecture_number = int(msg.text)
    if not (1 <= lecture_number <= len(lectures)):
        await msg.answer("⚠️ Некорректный номер лекции. Попробуйте снова.")
        return

    selected_lecture = lectures[lecture_number - 1]
    async with aiosqlite.connect("db/bot_database.db") as conn:
        async with conn.execute(
                "SELECT lecture FROM bookings WHERE direction = ? AND lecture = ?",
                (direction, selected_lecture)
        ) as cursor:
            if await cursor.fetchone():
                await msg.answer(f"⚠️ Лекция *'{selected_lecture}'* уже забронирована.", parse_mode="Markdown")
                return

        await conn.execute(
            "INSERT INTO bookings (user_id, lecture, direction) VALUES (?, ?, ?)",
            (msg.from_user.id, selected_lecture, direction)
        )
        await conn.commit()
        logging.info(f"User {msg.from_user.id} booked lecture: {selected_lecture} ({direction})")
        await msg.answer(f"✅ Лекция *'{selected_lecture}'* успешно забронирована!", parse_mode="Markdown")
        await state.clear()


@router.message(lambda message: message.text == "🔙 Возврат в меню")
async def return_to_menu(message: types.Message) -> None:
    """
    Возвращает пользователя в главное меню.
    """
    logging.info(f"User {message.from_user.id} returned to main menu.")
    await message.answer("Возвращаюсь в главное меню...", reply_markup=main_menu)


async def main() -> None:
    """
    Основная функция запуска бота.
    """
    logging.info("Bot is starting...")
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
