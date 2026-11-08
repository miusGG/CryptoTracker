from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tgbot.i18n import t


def button(lang, key, action):
    return InlineKeyboardButton(text=t(lang, key), callback_data=action)


def menu_keyboard(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [button(lang, "alerts", "alerts")],
        [button(lang, "create", "add_alert"), button(lang, "price_button", "check_price")],
        [button(lang, "settings_button", "settings")],
    ])


def settings_keyboard(autostart=False, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("✓ " if not autostart else "") + t(lang, "off_default"), callback_data="autostart:0")],
        [InlineKeyboardButton(text=("✓ " if autostart else "") + t(lang, "on_default"), callback_data="autostart:1")],
        [InlineKeyboardButton(text=("✓ " if lang == "ru" else "") + "🇷🇺 Русский", callback_data="language:ru"),
         InlineKeyboardButton(text=("✓ " if lang == "en" else "") + "🇬🇧 English", callback_data="language:en")],
        [button(lang, "home", "menu")],
    ])


def symbol_is_keyboard(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [button(lang, "symbol", "is_symbol"), button(lang, "coin_id", "is_name")],
        [button(lang, "home", "menu")],
    ])


def symbol_is_for_check_price(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [button(lang, "symbol", "is_symbol_check_price"), button(lang, "coin_id", "is_name_check_price")],
        [button(lang, "home", "menu")],
    ])


def back_to_alerts_keyboard(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[[button(lang, "back_alerts", "alerts")]])
