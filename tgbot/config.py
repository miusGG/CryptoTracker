from dataclasses import dataclass
import json


@dataclass
class TgBot:
    token: str
    admins_ids: list[int]


@dataclass
class Config:
    tg_bot: TgBot


def load_config(path):
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get("main"), dict):
        raise ValueError("cfg.json must contain a main object")
    main = data["main"]
    token = main.get("BOT_TOKEN")
    if not isinstance(token, str) or not token or token == "PASTE_TELEGRAM_BOT_TOKEN_HERE":
        raise ValueError("Set main.BOT_TOKEN to the token from @BotFather")
    admins = main.get("ADMINS", [])
    if not isinstance(admins, list) or any(type(value) is not int or value <= 0 for value in admins):
        raise ValueError("main.ADMINS must be a list of positive Telegram user IDs")
    if not isinstance(main.get("PASSWORD", ""), str):
        raise ValueError("main.PASSWORD must be a string (empty disables password registration)")
    if main.get("language", "ru") not in ("ru", "en"):
        raise ValueError("main.language must be ru or en")
    if main.get("autostart", False) not in (0, 1):
        raise ValueError("main.autostart must be true/false or 0/1")
    currency = main.get("currency", "USDT")
    if not isinstance(currency, str) or not currency or not currency.isascii() or not currency.isalpha():
        raise ValueError("main.currency must be a currency code such as USD or EUR")
    return Config(tg_bot=TgBot(token=token, admins_ids=admins))
