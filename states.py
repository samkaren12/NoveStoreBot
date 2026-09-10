from aiogram.fsm.state import State, StatesGroup


class SupportState(StatesGroup):
    waiting_message = State()


class OwnerReplyState(StatesGroup):
    waiting_message = State()


class BackupState(StatesGroup):
    waiting_file = State()


class ProductState(StatesGroup):
    name = State()
    description = State()
    price = State()
    stock = State()
    photo = State()


class EditProductState(StatesGroup):
    name = State()
    description = State()
    price = State()
    stock = State()
    photo = State()


class BroadcastState(StatesGroup):
    message = State()


class CardState(StatesGroup):
    title = State()
    number = State()
    holder = State()


class EditCardState(StatesGroup):
    title = State()
    number = State()
    holder = State()


class MenuButtonState(StatesGroup):
    label = State()
    color = State()
    order = State()


class ShopNameState(StatesGroup):
    waiting_name = State()


class AdminState(StatesGroup):
    user_id = State()
    permissions = State()


class ChannelState(StatesGroup):
    chat_id = State()
    title = State()
    link = State()
