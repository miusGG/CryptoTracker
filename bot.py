import asyncio
import json
import logging
import platform

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from crypto import CoinGekoCryptoService, cfg_path
from tgbot.config import load_config, Config
from tgbot.handlers import routers_list
from tgbot.i18n import t
from tgbot.middlewares.config import ConfigMiddleware
from tgbot.services import broadcaster
from tgbot.services.diagnostics import error_context

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, admin_ids: list[int], lang="ru"):
    await broadcaster.broadcast(bot, admin_ids, t(lang, "startup"))


def register_global_middlewares(dp: Dispatcher, config: Config):
    middleware = ConfigMiddleware(config)
    dp.message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    for name in ("httpx", "httpcore", "aiogram.event"):
        logging.getLogger(name).setLevel(logging.WARNING)


async def on_error(event: ErrorEvent, crypt: CoinGekoCryptoService):
    logger.error("HANDLER_FAILED update_id=%s update_type=%s %s; check configuration and connectivity",
                 event.update.update_id, event.update.event_type, error_context(event.exception))
    try:
        lang = crypt.get_language()
    except (OSError, ValueError):
        lang = "ru"
    if event.update.callback_query:
        await event.update.callback_query.answer(t(lang, "handler_error"), show_alert=True)
    elif event.update.message:
        await event.update.message.answer(t(lang, "handler_error"))
    return True


async def main():
    setup_logging()
    logger.info("BOT_STARTING version=1.0 python=%s config=%s", platform.python_version(), cfg_path)
    try:
        config = load_config(cfg_path)
    except FileNotFoundError:
        logger.error("CONFIG_MISSING copy cfg_example.json to cfg.json and fill in BOT_TOKEN and ADMINS")
        raise SystemExit(1)
    except json.JSONDecodeError as error:
        logger.error("CONFIG_INVALID_JSON line=%s column=%s; check commas and quotes", error.lineno, error.colno)
        raise SystemExit(1)
    except (OSError, ValueError) as error:
        logger.error("CONFIG_INVALID %s", error)
        raise SystemExit(1)

    bot = None
    crypt = None
    stage = "telegram_auth"
    try:
        bot = Bot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode="HTML"))
        identity = await bot.me()
        logger.info("TELEGRAM_CONNECTED bot_id=%s username=@%s", identity.id, identity.username)
        stage = "service_setup"
        dp = Dispatcher(storage=MemoryStorage())
        crypt = CoinGekoCryptoService(bot=bot)
        dp["crypt"] = crypt
        dp.include_routers(*routers_list)
        dp.errors.register(on_error)
        register_global_middlewares(dp, config)
        logger.info("CONFIG_LOADED currency=%s language=%s autostart=%s admins=%s alerts=%s",
                    crypt.currency, crypt.get_language(), int(crypt.get_autostart()),
                    len(config.tg_bot.admins_ids), len(crypt.list_tasks()))
        stage = "restore_alerts"
        await crypt.start_background()
        if not config.tg_bot.admins_ids:
            logger.warning("NO_ADMINS notifications have no recipients; configure ADMINS or register with PASSWORD")
        stage = "startup_notifications"
        await on_startup(bot, config.tg_bot.admins_ids, crypt.get_language())
        stage = "polling"
        logger.info("BOT_READY polling=true language=%s admins=%s; open Telegram /menu; Ctrl+C to stop",
                    crypt.get_language(), len(config.tg_bot.admins_ids))
        await dp.start_polling(bot, close_bot_session=False)
    except Exception as error:
        logger.error("BOT_FAILED stage=%s %s; check token, configuration and network", stage, error_context(error))
        raise SystemExit(1)
    finally:
        logger.info("BOT_STOPPING stage=%s; cancelling background requests and closing Telegram session", stage)
        if crypt is not None:
            await crypt.close()
        if bot is not None:
            await bot.session.close()
        logger.info("BOT_STOPPED enabled alerts will resume on next start")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as error:
        if isinstance(error, SystemExit):
            raise
        logging.getLogger(__name__).info("BOT_INTERRUPTED by keyboard")
