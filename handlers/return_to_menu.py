import logging
from aiogram import types, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from config import main_menu  # Убедитесь, что переменная main_menu импортируется правильно

router = Router()

@router.message(StateFilter(None), lambda message: message.text == "🔙 Возврат в меню")
async def return_to_menu(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик для возврата в главное меню.
    Очищает текущее состояние FSM и отправляет пользователю главное меню.
    """
    await state.clear()  # Сбрасываем текущее состояние
    logging.info(f"User {message.from_user.id} returned to main menu.")
    await message.answer("Возвращаюсь в главное меню...", reply_markup=main_menu)
