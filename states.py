from aiogram.fsm.state import State, StatesGroup


class AdminCategoryStates(StatesGroup):
    waiting_name = State()
    waiting_emoji = State()
    edit_name = State()
    edit_emoji = State()


class AdminProductStates(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_category = State()
    waiting_photo = State()
    waiting_keys = State()
    edit_field = State()


class AdminPromocodeStates(StatesGroup):
    waiting_code = State()
    waiting_type = State()
    waiting_value = State()
    waiting_uses = State()


class AdminAIPromptStates(StatesGroup):
    waiting_prompt = State()


class AdminBroadcastState(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()


class AdminSettingsStates(StatesGroup):
    waiting_custom_text = State()
    waiting_crypto_fee = State()


class DepositStates(StatesGroup):
    waiting_amount = State()
    waiting_promo = State()


class SupportState(StatesGroup):
    waiting_question = State()
