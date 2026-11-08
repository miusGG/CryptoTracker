from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from tgbot.i18n import t


def above_below_keyboard(lang="ru"):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "above")), KeyboardButton(text=t(lang, "below"))]],
        resize_keyboard=True,
        input_field_placeholder=t(lang, "direction_hint"),
    )
