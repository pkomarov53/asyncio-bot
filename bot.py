import asyncio
import os
import logging
from pathlib import Path
from functools import lru_cache

import aiosqlite
import aiofiles
from aiogram import Bot, Dispatcher, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from aiogram.filters import Command

# Настройка логгера
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загрузка токена из переменных окружения
TOKEN = ""

# Константы для путей
BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "bot_database.db"
BOOKS_DIR = BASE_DIR / "books"
USEFUL_INFO_DIR = BASE_DIR / "useful_info"
LECTIONS_DIR = BASE_DIR / "lections"

# Инициализация бота, диспетчера и роутера
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# Состояния бронирования лекций
class BookingState(StatesGroup):
    waiting_for_direction = State()
    waiting_for_lecture = State()


async def init_db() -> None:
    """
    Инициализация базы данных с созданием необходимых таблиц.
    """
    DB_DIR.mkdir(exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as conn:
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
    logger.info("Database initialized successfully.")


@lru_cache(maxsize=None)
def get_file_base_names(folder: Path, extensions: tuple) -> list:
    """
    Возвращает список имён файлов (без расширений) из указанной папки.
    Используется кэширование для повышения производительности.
    """
    folder.mkdir(exist_ok=True)
    return [file.stem for file in folder.iterdir() if file.suffix in extensions]


def get_buttons(folder: Path, extensions: tuple) -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру с кнопками на основе имён файлов из указанной папки.
    """
    base_names = get_file_base_names(folder, extensions)
    buttons = [[KeyboardButton(text=name)] for name in base_names]
    buttons.append([KeyboardButton(text="🔙 Возврат в меню")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)


async def read_file_content_async(file_path: Path, encoding: str = "utf-8") -> str:
    """
    Асинхронно читает содержимое файла.
    """
    async with aiofiles.open(file_path, "r", encoding=encoding) as file:
        content = await file.read()
    return content.strip()


async def read_lines_async(file_path: Path, encoding: str = "utf-8") -> list:
    """
    Асинхронно читает строки из файла, возвращая непустые строки.
    """
    content = await read_file_content_async(file_path, encoding)
    return [line.strip() for line in content.splitlines() if line.strip()]


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
    Команда /start – регистрация пользователя в БД и вывод главного меню.
    """
    telegram_id = message.from_user.id
    nickname = message.from_user.username or message.from_user.full_name
    logger.info("User @%s (ID: %s) started the bot.", nickname, telegram_id)
    async with aiosqlite.connect(str(DB_PATH)) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, nickname) VALUES (?, ?)",
            (telegram_id, nickname)
        )
        await conn.commit()
    await message.answer(
        f"Привет, @{nickname}! Добро пожаловать в бот контент-отдела!",
        reply_markup=main_menu
    )


@router.message(lambda message: message.text == "📚 Ссылки на книги")
async def book_links_menu(message: types.Message) -> None:
    """
    Вывод меню с направлениями книг.
    """
    logger.info("User %s accessed Book Links menu.", message.from_user.id)
    await message.answer("Выбери направление:", reply_markup=get_buttons(BOOKS_DIR, (".txt",)))


@router.message(lambda message: message.text in get_file_base_names(BOOKS_DIR, (".txt",)))
async def send_book_link(message: types.Message) -> None:
    """
    Отправка ссылки на книгу.
    """
    book_file = BOOKS_DIR / f"{message.text}.txt"
    if book_file.exists():
        book_link = await read_file_content_async(book_file)
        logger.info("User %s requested book: %s", message.from_user.id, message.text)
        await message.answer(f"Вот ссылка на литературу: https://{book_link}")
    else:
        await message.answer("❌ Книга не найдена.")


@router.message(lambda message: message.text == "ℹ️ Полезная информация")
async def useful_info_menu(message: types.Message) -> None:
    """
    Вывод меню с полезной информацией.
    """
    logger.info("User %s accessed Useful Information menu.", message.from_user.id)
    await message.answer(
        "Нажми на кнопку, чтобы получить полезную информацию:",
        reply_markup=get_buttons(USEFUL_INFO_DIR, (".txt", ".pdf"))
    )


@router.message(lambda message: message.text in get_file_base_names(USEFUL_INFO_DIR, (".txt", ".pdf")))
async def send_useful_info(message: types.Message) -> None:
    """
    Отправка полезной информации: текст или PDF.
    """
    info_txt = USEFUL_INFO_DIR / f"{message.text}.txt"
    info_pdf = USEFUL_INFO_DIR / f"{message.text}.pdf"
    if info_txt.exists():
        info_text = await read_file_content_async(info_txt)
        logger.info("User %s requested info: %s", message.from_user.id, message.text)
        await message.answer(info_text)
    elif info_pdf.exists():
        logger.info("User %s requested PDF: %s", message.from_user.id, message.text)
        await message.answer_document(FSInputFile(str(info_pdf)))
    else:
        await message.answer("❌ Информация не найдена.")


@router.message(lambda message: message.text == "📅 Доступные лекции")
async def available_lectures_menu(message: types.Message, state: FSMContext) -> None:
    """
    Вывод меню с направлениями лекций.
    """
    logger.info("User %s accessed Available Lectures menu.", message.from_user.id)
    await message.answer("Выбери направление лекций:", reply_markup=get_buttons(LECTIONS_DIR, (".txt",)))
    await state.set_state(BookingState.waiting_for_direction)


@router.message(lambda message: message.text in get_file_base_names(LECTIONS_DIR, (".txt",)))
async def show_lectures(message: types.Message, state: FSMContext) -> None:
    """
    Отображение списка лекций для выбранного направления с индикаторами бронирования.
    """
    direction = message.text
    lection_file = LECTIONS_DIR / f"{direction}.txt"
    logger.info("Opening file for direction '%s': %s", direction, lection_file)
    if lection_file.exists():
        lectures = await read_lines_async(lection_file)
        async with aiosqlite.connect(str(DB_PATH)) as conn:
            async with conn.execute("SELECT lecture FROM bookings WHERE direction = ?", (direction,)) as cursor:
                rows = await cursor.fetchall()
                booked_lectures = {row[0] for row in rows}
        await state.update_data(direction=direction)
        lecture_list = "\n\n".join(
            f"{'🔴' if lecture in booked_lectures else '🟢'} {idx}. {lecture}"
            for idx, lecture in enumerate(lectures, start=1)
        )
        await message.answer(
            f"📖 *Доступные лекции в направлении* _{direction}_:\n\n{lecture_list}\n\n"
            "Введите номер лекции, чтобы забронировать.",
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

    lection_file = LECTIONS_DIR / f"{direction}.txt"
    if not lection_file.exists():
        await msg.answer("❌ Ошибка: направление не найдено.")
        return

    lectures = await read_lines_async(lection_file)
    lecture_number = int(msg.text)
    if not (1 <= lecture_number <= len(lectures)):
        await msg.answer("⚠️ Некорректный номер лекции. Попробуйте снова.")
        return

    selected_lecture = lectures[lecture_number - 1]
    async with aiosqlite.connect(str(DB_PATH)) as conn:
        async with conn.execute(
            "SELECT lecture FROM bookings WHERE direction = ? AND lecture = ?",
            (direction, selected_lecture)
        ) as cursor:
            if await cursor.fetchone():
                await msg.answer(
                    f"⚠️ Лекция *'{selected_lecture}'* уже забронирована.",
                    parse_mode="Markdown"
                )
                return

        await conn.execute(
            "INSERT INTO bookings (user_id, lecture, direction) VALUES (?, ?, ?)",
            (msg.from_user.id, selected_lecture, direction)
        )
        await conn.commit()
    logger.info("User %s booked lecture: %s (%s)", msg.from_user.id, selected_lecture, direction)
    await msg.answer(f"✅ Лекция *'{selected_lecture}'* успешно забронирована!", parse_mode="Markdown")
    await state.clear()


@router.message(lambda message: message.text == "📖 Мои лекции")
async def my_lectures(message: types.Message) -> None:
    """
    Отображение списка забронированных лекций с inline-кнопками.
    """
    user_id = message.from_user.id
    async with aiosqlite.connect(str(DB_PATH)) as conn:
        async with conn.execute(
            "SELECT id, lecture, direction FROM bookings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("📭 У вас нет забронированных лекций.")
        return

    text = "📖 *Ваши лекции:*\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for i, (lecture_id, lecture, direction) in enumerate(rows, start=1):
        text += f"📌 *{i}. {lecture}* ({direction})\n\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"✔ Завершить {i}", callback_data=f"complete:{lecture_id}"),
            InlineKeyboardButton(text=f"❌ Отменить {i}", callback_data=f"cancel:{lecture_id}")
        ])

    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(lambda call: call.data.startswith(("complete:", "cancel:")))
async def manage_lecture_callback(call: CallbackQuery) -> None:
    """
    Обработка завершения или отмены лекции через inline-кнопки.
    """
    user_id = call.from_user.id
    action, lecture_id = call.data.split(":", 1)
    async with aiosqlite.connect(str(DB_PATH)) as conn:
        async with conn.execute(
            "SELECT lecture FROM bookings WHERE id = ? AND user_id = ?",
            (lecture_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                await call.answer("⚠ Лекция не найдена.", show_alert=True)
                return
            lecture_name = row[0]
        await conn.execute("DELETE FROM bookings WHERE id = ? AND user_id = ?", (lecture_id, user_id))
        await conn.commit()

    if action == "complete":
        await call.message.edit_text(
            f"✅ Лекция *'{lecture_name}'* завершена!", parse_mode="Markdown"
        )
    else:
        await call.message.edit_text(
            f"🔄 Лекция *'{lecture_name}'* отменена.", parse_mode="Markdown"
        )

    await call.answer("✅ Действие выполнено!")


@router.message(lambda message: message.text == "🔙 Возврат в меню")
async def return_to_menu(message: types.Message) -> None:
    """
    Возвращение пользователя в главное меню.
    """
    logger.info("User %s returned to main menu.", message.from_user.id)
    await message.answer("Возвращаюсь в главное меню...", reply_markup=main_menu)


async def main() -> None:
    """
    Основная функция запуска бота.
    """
    logger.info("Bot is starting...")
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
