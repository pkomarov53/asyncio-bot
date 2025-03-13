from aiogram.fsm.state import StatesGroup, State

class BookingState(StatesGroup):
    waiting_for_direction = State()
    waiting_for_lecture = State()
