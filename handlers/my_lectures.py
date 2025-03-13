import logging
import aiosqlite
from aiogram import types, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

router = Router()

@router.message(lambda message: message.text == "📖 Мои лекции")
async def my_lectures(message: types.Message) -> None:
    """
    Отображение списка забронированных лекций с inline-кнопками.
    """
    user_id = message.from_user.id
    async with aiosqlite.connect("database/bot_database.database") as conn:
        async with conn.execute(
            "SELECT id, lecture, direction FROM bookings WHERE user_id = ?", (user_id,)
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
async def manage_lecture_callback(call: types.CallbackQuery) -> None:
    """
    Обработка завершения или отмены лекции через inline-кнопки.
    """
    user_id = call.from_user.id
    action, lecture_id = call.data.split(":", 1)
    async with aiosqlite.connect("database/bot_database.database") as conn:
        async with conn.execute("SELECT lecture FROM bookings WHERE id = ? AND user_id = ?", (lecture_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await call.answer("⚠ Лекция не найдена.", show_alert=True)
                return
            lecture_name = row[0]
        await conn.execute("DELETE FROM bookings WHERE id = ? AND user_id = ?", (lecture_id, user_id))
        await conn.commit()

    if action == "complete":
        await call.message.edit_text(f"✅ Лекция *'{lecture_name}'* завершена!", parse_mode="Markdown")
    else:
        await call.message.edit_text(f"🔄 Лекция *'{lecture_name}'* отменена.", parse_mode="Markdown")

    await call.answer("✅ Действие выполнено!")
