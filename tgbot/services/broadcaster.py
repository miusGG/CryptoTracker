import asyncio
import logging
from aiogram import Bot, exceptions
from aiogram.types import InlineKeyboardMarkup
from tgbot.services.diagnostics import error_context

logger = logging.getLogger(__name__)


async def send_message(bot: Bot, user_id: int | str, text: str,
                       disable_notification=False, reply_markup: InlineKeyboardMarkup = None) -> bool:
    while True:
        try:
            await bot.send_message(user_id, text, disable_notification=disable_notification, reply_markup=reply_markup)
        except exceptions.TelegramRetryAfter as error:
            logger.warning("TELEGRAM_RATE_LIMIT user_id=%s retry_seconds=%s", user_id, error.retry_after)
            await asyncio.sleep(error.retry_after)
            continue
        except exceptions.TelegramForbiddenError:
            logger.warning("TELEGRAM_FORBIDDEN user_id=%s; open the bot and press Start or unblock it", user_id)
        except exceptions.TelegramBadRequest:
            logger.error("TELEGRAM_BAD_REQUEST user_id=%s; check chat ID and message format", user_id)
        except exceptions.TelegramAPIError as error:
            logger.error("TELEGRAM_SEND_FAILED user_id=%s %s; check Telegram connectivity", user_id, error_context(error))
        else:
            logger.info("TELEGRAM_SENT user_id=%s", user_id)
            return True
        return False


async def broadcast(bot: Bot, users: list[int | str], text: str,
                    disable_notification=False, reply_markup: InlineKeyboardMarkup = None) -> int:
    count = 0
    for user_id in users:
        if await send_message(bot, user_id, text, disable_notification, reply_markup):
            count += 1
        await asyncio.sleep(0.05)
    logger.info("BROADCAST_DONE sent=%s total=%s", count, len(users))
    return count
