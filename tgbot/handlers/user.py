from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram import Router, F

from crypto import CoinGekoCryptoService
from tgbot.config import Config
from tgbot.i18n import t

user_router = Router()


@user_router.message(CommandStart())
async def user_start(message: Message, lang="ru"):
    await message.answer(t(lang, "welcome", name=message.from_user.first_name))


@user_router.message(F.text)
async def guess_failed(message: Message, crypt: CoinGekoCryptoService, config: Config, lang="ru"):
    if crypt.authorize_admin(message.from_user.id, message.text):
        if message.from_user.id not in config.tg_bot.admins_ids:
            config.tg_bot.admins_ids.append(message.from_user.id)
        await message.answer(t(lang, "authorized"))
    else:
        await message.answer(t(lang, "unknown"))
