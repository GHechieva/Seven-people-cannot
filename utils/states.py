from aiogram.fsm.state import State, StatesGroup


class TripCreateStates(StatesGroup):
    name = State()
    description = State()
    currency = State()


class TripJoinStates(StatesGroup):
    code = State()


class ExpenseStates(StatesGroup):
    select_trip = State()
    description = State()
    amount = State()
    currency = State()
    payer = State()
    category = State()
    participants = State()
    split_type = State()
    custom_percentages = State()
    confirm = State()


class EditExpenseStates(StatesGroup):
    new_description = State()


class ReceiptStates(StatesGroup):
    waiting_confirm = State()
    description = State()
    amount = State()
    currency = State()
    payer = State()
    category = State()
    participants = State()
    split_type = State()


class NotificationStates(StatesGroup):
    timezone = State()
