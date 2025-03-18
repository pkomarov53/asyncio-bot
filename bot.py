import asyncio
import logging
import os
from pathlib import Path
from functools import lru_cache
from typing import List, Tuple, AsyncIterator, Any

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
from aiogram.filters import Command, BaseFilter
from contextlib import asynccontextmanager

# =======================
# Конфигурация
# =======================
class Config:
    """
    Класс для хранения конфигурационных констант.
    """
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    BASE_DIR: Path = Path(__file__).parent
    DB_DIR: Path = BASE_DIR / "db"
    DB_PATH: Path = DB_DIR / "bot_database.db"
    BOOKS_DIR: Path = BASE_DIR / "books"
    USEFUL_INFO_DIR: Path = BASE_DIR / "useful_info"
    LECTIONS_DIR: Path = BASE_DIR / "lections"
    SPECIAL_USERS: List[int] = [473516172, 380771755]
    DB_POOL_SIZE: int = 5

# =======================
# Менеджер базы данных (пул соединений)
# =======================
class DatabaseManager:
    """
    Менеджер пула соединений для безопасного и эффективного доступа к базе данных.
    """
    def __init__(self, db_path: Path, pool_size: int = 5) -> None:
        self.db_path = db_path
        self.pool_size = pool_size
        self.pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=pool_size)

    async def init_pool(self) -> None:
        """
        Инициализирует пул соединений.
        """
        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(str(self.db_path))
            conn.row_factory = aiosqlite.Row
            await self.pool.put(conn)
        logging.info("Пул соединений инициализирован (размер %d)", self.pool_size)

    async def close_pool(self) -> None:
        """
        Закрывает все соединения в пуле.
        """
        while not self.pool.empty():
            conn = await self.pool.get()
            await conn.close()
        logging.info("Пул соединений закрыт.")

    async def acquire(self) -> aiosqlite.Connection:
        """
        Получает соединение из пула.
        """
        return await self.pool.get()

    async def release(self, conn: aiosqlite.Connection) -> None:
        """
        Возвращает соединение обратно в пул.
        """
        await self.pool.put(conn)

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Асинхронный контекстный менеджер для работы с соединением из пула.
        """
        conn = await self.acquire()
        try:
            yield conn
        except Exception as e:
            logging.error("Ошибка при работе с БД: %s", e)
            raise
        finally:
            await self.release(conn)

# =======================
# Кастомные фильтры
# =======================
class IsSpecialUser(BaseFilter):
    """
    Фильтр для проверки, является ли пользователь администратором.
    """
    def __init__(self, special_users: List[int]) -> None:
        self.special_users = special_users

    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id in self.special_users

# =======================
# Утилиты для работы с файлами
# =======================
async def read_file_content_async(file_path: Path, encoding: str = "utf-8") -> str:
    """
    Асинхронно читает содержимое файла.
    """
    async with aiofiles.open(file_path, "r", encoding=encoding) as file:
        content = await file.read()
    return content.strip()

async def read_lines_async(file_path: Path, encoding: str = "utf-8") -> List[str]:
    """
    Асинхронно читает строки из файла, возвращая непустые строки.
    """
    content = await read_file_content_async(file_path, encoding)
    return [line.strip() for line in content.splitlines() if line.strip()]

async def remove_line_from_file(file_path: Path, line_to_remove: str, encoding: str = "utf-8") -> None:
    """
    Асинхронно удаляет указанную строку из файла.
    """
    lines = await read_lines_async(file_path, encoding)
    lines = [line for line in lines if line.strip() != line_to_remove.strip()]
    async with aiofiles.open(file_path, "w", encoding=encoding) as file:
        await file.write("\n".join(lines))

# =======================
# Класс для формирования клавиатур
# =======================
class KeyboardBuilder:
    """
    Генерирует клавиатуры на основе содержимого директорий.
    """
    @staticmethod
    @lru_cache(maxsize=None)
    def get_file_base_names(folder: Path, extensions: Tuple[str, ...]) -> List[str]:
        """
        Возвращает отсортированный список имён файлов (без расширений) из указанной папки.
        """
        folder.mkdir(exist_ok=True)
        return sorted([file.stem for file in folder.iterdir() if file.suffix in extensions])

    @staticmethod
    def build_keyboard(folder: Path, extensions: Tuple[str, ...]) -> ReplyKeyboardMarkup:
        """
        Строит клавиатуру с кнопками на основе имён файлов.
        """
        base_names = KeyboardBuilder.get_file_base_names(folder, extensions)
        buttons = [[KeyboardButton(text=name)] for name in base_names]
        buttons.append([KeyboardButton(text="🔙 Возврат в меню")])
        return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

    @staticmethod
    def main_menu(is_special: bool = False) -> ReplyKeyboardMarkup:
        """
        Строит главное меню.
        """
        buttons = [
            [KeyboardButton(text="📚 Ссылки на книги")],
            [KeyboardButton(text="ℹ️ Полезная информация")],
            [KeyboardButton(text="📅 Доступные лекции")],
            [KeyboardButton(text="📖 Мои лекции")]
        ]
        if is_special:
            buttons.append([KeyboardButton(text="👑 Админ-панель")])
        return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

# =======================
# Компонент бизнес-логики (BotService)
# =======================
class BotService:
    """
    Класс, инкапсулирующий бизнес-логику бота.
    """
    def __init__(self, db_manager: DatabaseManager, config: Config) -> None:
        self.db_manager = db_manager
        self.config = config

    async def init_db(self) -> None:
        """
        Инициализирует базу данных и создаёт необходимые таблицы.
        """
        self.config.DB_DIR.mkdir(exist_ok=True)
        async with self.db_manager.get_connection() as conn:
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
        logging.info("База данных инициализирована.")

    async def register_user(self, message: types.Message) -> None:
        """
        Регистрирует пользователя в базе данных.
        """
        telegram_id = message.from_user.id
        nickname = message.from_user.username or message.from_user.full_name
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO users (telegram_id, nickname) VALUES (?, ?)",
                (telegram_id, nickname)
            )
            await conn.commit()
        logging.info("Пользователь @%s (ID: %s) зарегистрирован.", nickname, telegram_id)

    async def get_book_link(self, book_name: str) -> str:
        """
        Получает ссылку на книгу из директории BOOKS_DIR.
        """
        book_file = self.config.BOOKS_DIR / f"{book_name}.txt"
        if book_file.exists():
            content = await read_file_content_async(book_file)
            return f"https://{content}"
        raise FileNotFoundError("Книга не найдена.")

    async def get_useful_info(self, info_name: str) -> Tuple[str, str]:
        """
        Получает полезную информацию.
        Возвращает кортеж: (тип информации: "text" или "pdf", содержимое или путь к файлу).
        """
        info_txt = self.config.USEFUL_INFO_DIR / f"{info_name}.txt"
        info_pdf = self.config.USEFUL_INFO_DIR / f"{info_name}.pdf"
        if info_txt.exists():
            content = await read_file_content_async(info_txt)
            return ("text", content)
        elif info_pdf.exists():
            return ("pdf", str(info_pdf))
        raise FileNotFoundError("Полезная информация не найдена.")

    async def get_available_lectures(self, direction: str) -> List[str]:
        """
        Получает список доступных лекций для указанного направления.
        """
        lection_file = self.config.LECTIONS_DIR / f"{direction}.txt"
        if not lection_file.exists():
            raise FileNotFoundError(f"Направление '{direction}' не найдено.")
        lectures = await read_lines_async(lection_file)
        async with self.db_manager.get_connection() as conn:
            async with conn.execute("SELECT lecture FROM bookings WHERE direction = ?", (direction,)) as cursor:
                rows = await cursor.fetchall()
                booked_lectures = {row["lecture"] for row in rows}
        return [
            f"{'🔴' if lecture in booked_lectures else '🟢'} {idx}. {lecture}"
            for idx, lecture in enumerate(lectures, start=1)
        ]

    async def book_lecture(self, user_id: int, direction: str, lecture_number: int) -> str:
        """
        Бронирует лекцию для пользователя.
        """
        lection_file = self.config.LECTIONS_DIR / f"{direction}.txt"
        if not lection_file.exists():
            raise FileNotFoundError("Направление не найдено.")
        lectures = await read_lines_async(lection_file)
        if not (1 <= lecture_number <= len(lectures)):
            raise ValueError("Некорректный номер лекции.")
        selected_lecture = lectures[lecture_number - 1]
        async with self.db_manager.get_connection() as conn:
            async with conn.execute(
                "SELECT lecture FROM bookings WHERE direction = ? AND lecture = ?",
                (direction, selected_lecture)
            ) as cursor:
                if await cursor.fetchone():
                    raise ValueError("Лекция уже забронирована.")
            await conn.execute(
                "INSERT INTO bookings (user_id, lecture, direction) VALUES (?, ?, ?)",
                (user_id, selected_lecture, direction)
            )
            await conn.commit()
        logging.info("Пользователь %s забронировал лекцию: %s (%s)", user_id, selected_lecture, direction)
        return selected_lecture

    async def get_user_lectures(self, user_id: int) -> List[aiosqlite.Row]:
        """
        Получает список лекций, забронированных пользователем.
        """
        async with self.db_manager.get_connection() as conn:
            async with conn.execute(
                "SELECT id, lecture, direction FROM bookings WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return rows

    async def manage_lecture(self, user_id: int, lecture_id: int, action: str) -> Tuple[str, str]:
        """
        Завершает или отменяет бронь лекции.
        Возвращает сообщение результата и название лекции.
        """
        async with self.db_manager.get_connection() as conn:
            async with conn.execute(
                "SELECT lecture, direction FROM bookings WHERE id = ? AND user_id = ?",
                (lecture_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise ValueError("Лекция не найдена.")
                lecture_name, direction = row["lecture"], row["direction"]
            await conn.execute("DELETE FROM bookings WHERE id = ? AND user_id = ?", (lecture_id, user_id))
            await conn.commit()
        # Удаляем лекцию из файла, если требуется
        lection_file = self.config.LECTIONS_DIR / f"{direction}.txt"
        if lection_file.exists():
            await remove_line_from_file(lection_file, lecture_name)
        result_message = (
            f"✅ Лекция *'{lecture_name}'* завершена!" if action == "complete"
            else f"🔄 Лекция *'{lecture_name}'* отменена."
        )
        return result_message, lecture_name

# =======================
# FSM состояния для бронирования лекций
# =======================
class BookingState(StatesGroup):
    waiting_for_direction = State()
    waiting_for_lecture = State()

# =======================
# Регистрация хендлеров
# =======================
router = Router()

def register_handlers(dp: Dispatcher, bot_service: BotService, config: Config) -> None:
    """
    Регистрирует все хендлеры в диспетчере.
    """
    @router.message(Command("start"))
    async def start_handler(message: types.Message, state: FSMContext) -> None:
        """
        Обработка команды /start: регистрация пользователя и вывод главного меню.
        """
        await bot_service.register_user(message)
        is_special = message.from_user.id in config.SPECIAL_USERS
        menu = KeyboardBuilder.main_menu(is_special)
        await message.answer(
            f"Привет, @{message.from_user.username or message.from_user.full_name}! Добро пожаловать в бот контент-отдела!",
            reply_markup=menu
        )

    @router.message(IsSpecialUser(config.SPECIAL_USERS))
    @router.message(lambda message: message.text == "👑 Админ-панель")
    async def admin_panel_handler(message: types.Message) -> None:
        """
        Отображает все забронированные лекции для администраторов.
        """
        async with bot_service.db_manager.get_connection() as conn:
            async with conn.execute(
                "SELECT users.nickname, bookings.lecture, bookings.direction FROM bookings JOIN users ON bookings.user_id = users.telegram_id"
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await message.answer("📭 Нет забронированных лекций.")
            return
        text = "📖 *Все забронированные лекции:*\n\n"
        for i, row in enumerate(rows, start=1):
            text += f"👤 @{row['nickname']}: {row['lecture']} ({row['direction']})\n\n"
        await message.answer(text, parse_mode="Markdown")

    @router.message(lambda message: message.text == "📚 Ссылки на книги")
    async def book_links_handler(message: types.Message) -> None:
        """
        Выводит меню с категориями книг.
        """
        keyboard = KeyboardBuilder.build_keyboard(config.BOOKS_DIR, (".txt",))
        await message.answer("Выбери направление:", reply_markup=keyboard)

    @router.message(lambda message: message.text in KeyboardBuilder.get_file_base_names(config.BOOKS_DIR, (".txt",)))
    async def send_book_link_handler(message: types.Message) -> None:
        """
        Отправляет ссылку на выбранную книгу.
        """
        try:
            link = await bot_service.get_book_link(message.text)
            await message.answer(f"Вот ссылка на литературу: {link}")
        except FileNotFoundError:
            await message.answer("❌ Книга не найдена.")

    @router.message(lambda message: message.text == "ℹ️ Полезная информация")
    async def useful_info_handler(message: types.Message) -> None:
        """
        Выводит меню с категориями полезной информации.
        """
        keyboard = KeyboardBuilder.build_keyboard(config.USEFUL_INFO_DIR, (".txt", ".pdf"))
        await message.answer("Нажми на кнопку, чтобы получить полезную информацию:", reply_markup=keyboard)

    @router.message(lambda message: message.text in KeyboardBuilder.get_file_base_names(config.USEFUL_INFO_DIR, (".txt", ".pdf")))
    async def send_useful_info_handler(message: types.Message) -> None:
        """
        Отправляет выбранную полезную информацию (текст или PDF).
        """
        try:
            info_type, content = await bot_service.get_useful_info(message.text)
            if info_type == "text":
                await message.answer(content)
            else:
                await message.answer_document(FSInputFile(content))
        except FileNotFoundError:
            await message.answer("❌ Информация не найдена.")

    @router.message(lambda message: message.text == "📅 Доступные лекции")
    async def available_lectures_handler(message: types.Message, state: FSMContext) -> None:
        """
        Выводит меню с направлениями лекций.
        """
        keyboard = KeyboardBuilder.build_keyboard(config.LECTIONS_DIR, (".txt",))
        await message.answer("Выбери направление лекций:", reply_markup=keyboard)
        await state.set_state(BookingState.waiting_for_direction)

    @router.message(lambda message: message.text in KeyboardBuilder.get_file_base_names(config.LECTIONS_DIR, (".txt",)))
    async def show_lectures_handler(message: types.Message, state: FSMContext) -> None:
        """
        Показывает список лекций для выбранного направления.
        """
        direction = message.text
        try:
            lectures = await bot_service.get_available_lectures(direction)
            await state.update_data(direction=direction)
            lecture_list = "\n\n".join(lectures)
            await message.answer(
                f"📖 *Доступные лекции в направлении* _{direction}_:\n\n{lecture_list}\n\nВведите номер лекции, чтобы забронировать.",
                parse_mode="Markdown"
            )
            await state.set_state(BookingState.waiting_for_lecture)
        except FileNotFoundError:
            await message.answer(f"❌ Направление '{direction}' не найдено.")

    @router.message(lambda msg: msg.text.isdigit())
    async def book_lecture_handler(msg: types.Message, state: FSMContext) -> None:
        """
        Обрабатывает бронирование лекции.
        """
        user_data = await state.get_data()
        direction = user_data.get('direction')
        if not direction:
            await msg.answer("❌ Ошибка: не выбрано направление для бронирования.")
            return
        try:
            lecture_number = int(msg.text)
            selected_lecture = await bot_service.book_lecture(msg.from_user.id, direction, lecture_number)
            await msg.answer(f"✅ Лекция *'{selected_lecture}'* успешно забронирована!", parse_mode="Markdown")
            await state.clear()
        except (FileNotFoundError, ValueError) as e:
            await msg.answer(f"⚠️ {str(e)}")

    @router.message(lambda message: message.text == "📖 Мои лекции")
    async def my_lectures_handler(message: types.Message) -> None:
        """
        Отображает список лекций, забронированных пользователем, с inline-кнопками.
        """
        lectures = await bot_service.get_user_lectures(message.from_user.id)
        if not lectures:
            await message.answer("📭 У вас нет забронированных лекций.")
            return
        text = "📖 *Ваши лекции:*\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for i, row in enumerate(lectures, start=1):
            text += f"📌 *{i}. {row['lecture']}* ({row['direction']})\n\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=f"✔ Завершить {i}", callback_data=f"complete:{row['id']}"),
                InlineKeyboardButton(text=f"❌ Отменить {i}", callback_data=f"cancel:{row['id']}")
            ])
        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

    @router.callback_query(lambda call: call.data.startswith(("complete:", "cancel:")))
    async def manage_lecture_callback_handler(call: CallbackQuery) -> None:
        """
        Обрабатывает завершение или отмену лекции через inline-кнопки.
        """
        try:
            action, lecture_id_str = call.data.split(":", 1)
            lecture_id = int(lecture_id_str)
            result_message, _ = await bot_service.manage_lecture(call.from_user.id, lecture_id, action)
            await call.message.edit_text(result_message, parse_mode="Markdown")
            await call.answer("✅ Действие выполнено!")
        except (ValueError, Exception) as e:
            logging.error("Ошибка при управлении лекцией: %s", e)
            await call.answer("❌ Ошибка при выполнении действия.", show_alert=True)

    @router.message(lambda message: message.text == "🔙 Возврат в меню")
    async def return_to_menu_handler(message: types.Message) -> None:
        """
        Возвращает пользователя в главное меню.
        """
        is_special = message.from_user.id in config.SPECIAL_USERS
        menu = KeyboardBuilder.main_menu(is_special)
        await message.answer("Возвращаюсь в главное меню...", reply_markup=menu)

    dp.include_router(router)

# =======================
# Основная функция
# =======================
async def main() -> None:
    """
    Точка входа в приложение. Инициализирует все компоненты и запускает бота.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if not Config.BOT_TOKEN:
        logging.error("BOT_TOKEN не задан!")
        return

    # Инициализация конфигурации, пула соединений и бизнес-логики
    config = Config
    db_manager = DatabaseManager(config.DB_PATH, config.DB_POOL_SIZE)
    await db_manager.init_pool()
    bot_service = BotService(db_manager, config)

    # Инициализация бота и диспетчера
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    # Инициализация базы данных
    await bot_service.init_db()

    # Регистрация хендлеров
    register_handlers(dp, bot_service, config)

    logging.info("Бот запускается...")
    try:
        await dp.start_polling(bot)
    finally:
        await db_manager.close_pool()

if __name__ == "__main__":
    asyncio.run(main())
