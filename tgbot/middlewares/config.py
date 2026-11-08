import logging
from aiogram import BaseMiddleware

logger = logging.getLogger(__name__)


class ConfigMiddleware(BaseMiddleware):
    def __init__(self, config):
        self.config = config

    async def __call__(self, handler, event, data):
        data["config"] = self.config
        try:
            data["lang"] = data["crypt"].get_language()
        except (OSError, ValueError):
            data["lang"] = "ru"
            logger.warning("LANGUAGE_READ_FAILED fallback=ru")
        return await handler(event, data)
