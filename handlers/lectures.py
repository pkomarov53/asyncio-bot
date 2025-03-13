import os
import logging
import aiosqlite
from aiogram import types, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from config import main_menu
from states.booking_state import BookingState
from utils.file_utils import get_file_base_names, get_buttons, read_lines_async

router = Router()

@router.message(lambda message: message.text == "📅 Доступные лекции")
async def available_lectures_menu(message: types.Message, state: FSMContext) -> None:
    """
    Вывод меню с направлениями лекций.
    """
    logging.info(f"User {message.from_user.id} accessed Available Lectures menu.")
    await message.answer("Выбери направление лекций:", reply_markup=get_buttons("lections", (".txt",)))
    await state.set_state(BookingState.waiting_for_direction)

@router.message(lambda message: message.text in get_file_base_names("lections", (".txt",)))
async def show_lectures(message: types.Message, state: FSMContext) -> None:
    """
    Отображение списка лекций для выбранного направления с индикаторами бронирования.
    """
    direction = message.text
    lection_file = os.path.join("lections", f"{direction}.txt")
    logging.info(f"Opening file for direction '{direction}': {lection_file}")

    if os.path.exists(lection_file):
        lectures = await read_lines_async(lection_file)
        async with aiosqlite.connect("database/bot_database.database") as conn:
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

    lectures = await read_lines_async(lection_file)
    lecture_number = int(msg.text)
    if not (1 <= lecture_number <= len(lectures)):
        await msg.answer("⚠️ Некорректный номер лекции. Попробуйте снова.")
        return

    selected_lecture = lectures[lecture_number - 1]
    async with aiosqlite.connect("database/bot_database.database") as conn:
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

@router.message(StateFilter(None), lambda message: message.text == "🔙 Возврат в меню")
@router.message(lambda message: message.text == "🔙 Возврат в меню")  # В aiogram 3.x лучше так
async def return_to_menu(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик кнопки возврата в меню. Очищает состояние FSM и возвращает пользователя в главное меню.
    """
    await state.clear()  # Обнуляем состояние
    logging.info(f"User {message.from_user.id} returned to main menu.")
    await message.answer("Возвращаюсь в главное меню...", reply_markup=main_menu)