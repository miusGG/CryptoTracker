import asyncio
import hmac
import json
import logging
import math
import os
from pathlib import Path
import tempfile
from time import perf_counter

import httpx
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from tgbot.services.broadcaster import send_message
from tgbot.i18n import t
from tgbot.keyboards.inline import button
from tgbot.services.diagnostics import error_context

logger = logging.getLogger(__name__)
cfg_path = str(Path(__file__).resolve().with_name("cfg.json"))


class CoinGekoCryptoService:
    """JSON stores desired state; asyncio tasks run while the bot is alive."""

    def __init__(self, bot: Bot, exchange="binance", currency=None, config_path=cfg_path):
        self.bot = bot
        self.exchange = exchange
        self.currency = currency or self._read_currency(config_path)
        self.config_path = str(config_path)
        self._tasks = {}
        self._workers = {}
        self._supervisor = None
        self._closed = False
        self.sync_interval = 1.0
        self.retry_seconds = 60.0
        self.sync_tasks_from_file()

    @staticmethod
    def _read_currency(config_path):
        with open(config_path, encoding="utf-8") as file:
            return json.load(file).get("main", {}).get("currency", "USDT")

    def get_language(self):
        language = self._read_config().get("main", {}).get("language", "ru")
        return language if language in ("ru", "en") else "ru"

    def set_language(self, language):
        if language not in ("ru", "en"):
            return False
        data = self._read_config()
        data.setdefault("main", {})["language"] = language
        saved = self._write_config(data)
        if saved:
            logger.info("LANGUAGE_CHANGED language=%s", language)
        return saved

    def authorize_admin(self, user_id, password):
        data = self._read_config()
        expected = data.get("main", {}).get("PASSWORD", "")
        if not expected or not hmac.compare_digest(str(password).encode(), expected.encode()):
            return False
        admins = data["main"].setdefault("ADMINS", [])
        if user_id not in admins:
            admins.append(user_id)
            if not self._write_config(data):
                return False
            logger.info("ADMIN_ADDED user_id=%s", user_id)
        return True

    def _read_config(self):
        with open(self.config_path, encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("main", {}), dict):
            raise ValueError("Configuration must contain a main object")
        if not isinstance(data.get("tasks", {}), dict):
            raise ValueError("tasks must be an object")
        if any(not isinstance(task, dict) for task in data.get("tasks", {}).values()):
            raise ValueError("Each alert must be an object")
        return data

    def _write_config(self, data):
        """Replace the complete file atomically; never erase unreadable config."""
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=Path(self.config_path).parent,
                                             delete=False) as file:
                temporary = file.name
                json.dump(data, file, ensure_ascii=False, indent=4)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.config_path)
            self._tasks = data.get("tasks", {})
            return True
        except OSError as error:
            logger.error("CONFIG_SAVE_FAILED path=%s %s; check write permissions and free disk space",
                         self.config_path, error_context(error))
            return False
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _validate_task(task):
        if not isinstance(task["symbol"], str) or not task["symbol"].strip():
            raise ValueError("Укажите монету")
        for field in ("price", "time"):
            value = float(task[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Цена и интервал должны быть положительными числами")
        for field in ("is_above", "is_symbol", "is_running"):
            if task.get(field, 1) not in (0, 1):
                raise ValueError(f"{field} должен быть 0 или 1")

    def sync_tasks_from_file(self):
        data = self._read_config()
        self._tasks = data.get("tasks", {})

    def list_tasks(self):
        self.sync_tasks_from_file()
        return {key: dict(value) for key, value in self._tasks.items()}

    def get_autostart(self):
        return self._read_config().get("main", {}).get("autostart", False) == 1

    def set_autostart(self, enabled):
        data = self._read_config()
        data.setdefault("main", {})["autostart"] = bool(enabled)
        saved = self._write_config(data)
        if saved:
            logger.info("AUTOSTART_CHANGED enabled=%s", int(enabled))
        return saved

    def add_task(self, process_id: str, symbol: str, price: float, is_above: int,
                 time: float, note: str = "", is_symbol: int = 1) -> bool:
        data = self._read_config()
        tasks = data.setdefault("tasks", {})
        process_id = process_id.strip()
        if not process_id or process_id in tasks:
            return False
        task = {
            "is_symbol": int(is_symbol), "symbol": symbol.lower().strip(),
            "price": float(price), "is_above": int(is_above), "time": float(time),
            "is_running": int(data.get("main", {}).get("autostart", False) == 1),
            "note": note,
        }
        self._validate_task(task)
        tasks[process_id] = task
        saved = self._write_config(data)
        if saved:
            logger.info("ALERT_CREATED id=%r coin=%s enabled=%s interval_min=%s", process_id, task["symbol"], task["is_running"], task["time"])
        return saved

    def get_task_running_status(self, id: str):
        self.sync_tasks_from_file()
        return self._tasks.get(id, {}).get("is_running")

    async def start_background(self):
        """Restore enabled alerts, then watch changes in cfg.json."""
        self._closed = False
        await self.reconcile_tasks()
        enabled = sum(task.get("is_running") == 1 for task in self._tasks.values())
        logger.info("ALERTS_RESTORED total=%s enabled=%s running=%s disabled=%s invalid=%s",
                    len(self._tasks), enabled, len(self._workers), len(self._tasks) - enabled,
                    enabled - len(self._workers))
        if self._supervisor is None or self._supervisor.done():
            self._supervisor = asyncio.create_task(self._watch_config(), name="alert-supervisor")

    async def _watch_config(self):
        while True:
            await asyncio.sleep(self.sync_interval)
            try:
                await self.reconcile_tasks()
            except (OSError, ValueError, TypeError) as error:
                logger.warning("CONFIG_RELOAD_FAILED %s retry_seconds=%s; check JSON structure and permissions",
                               error_context(error), self.sync_interval)

    def _cancel_worker(self, task_id):
        worker = self._workers.get(task_id)
        if worker is not None:
            worker.cancel()
            logger.info("WORKER_CANCEL_REQUESTED id=%r", task_id)

    async def reconcile_tasks(self):
        # No awaits between reading desired state and registering workers.
        if self._closed:
            return
        self.sync_tasks_from_file()
        for task_id, worker in list(self._workers.items()):
            if worker.done():
                del self._workers[task_id]
            elif self._tasks.get(task_id, {}).get("is_running") != 1:
                self._cancel_worker(task_id)
        for task_id, task in self._tasks.items():
            if task.get("is_running") != 1 or task_id in self._workers:
                continue
            try:
                self._validate_task(task)
            except (KeyError, TypeError, ValueError):
                logger.error("ALERT_INVALID id=%r; check symbol, price, time and 0/1 flags", task_id)
                continue
            worker = asyncio.create_task(self._run_alert(task_id), name=f"price-alert:{task_id}")
            self._workers[task_id] = worker
            worker.add_done_callback(self._worker_done)
            logger.info("ALERT_STARTED id=%r coin=%r lookup=%s condition=%s target=%s currency=%s interval_min=%s",
                        task_id, task["symbol"], "symbol" if task.get("is_symbol", 1) else "id",
                        ">=" if task["is_above"] else "<=", task["price"], self.currency, task["time"])

    @staticmethod
    def _worker_done(worker):
        if worker.cancelled():
            logger.info("WORKER_STOPPED name=%r", worker.get_name())
        elif worker.exception() is not None:
            logger.error("WORKER_FAILED name=%r %s", worker.get_name(), error_context(worker.exception()))
        else:
            logger.info("WORKER_FINISHED name=%r", worker.get_name())

    async def close(self):
        """Stop in-memory work without changing flags, allowing restart recovery."""
        self._closed = True
        pending = list(self._workers.values())
        if self._supervisor is not None:
            pending.append(self._supervisor)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self._workers.clear()
        self._supervisor = None
        logger.info("ALERT_SERVICE_CLOSED saved_flags_preserved=true")

    async def start_price_alert_by_id(self, loop_id: str) -> bool:
        data = self._read_config()
        task = data.get("tasks", {}).get(loop_id)
        if task is None:
            logger.warning("ALERT_NOT_FOUND id=%r action=start", loop_id)
            return False
        try:
            self._validate_task(task)
        except (KeyError, TypeError, ValueError):
            return False
        if task.get("is_running") != 1:
            task["is_running"] = 1
            if not self._write_config(data):
                return False
        await self.reconcile_tasks()
        return True

    async def start_price_alert(self, loop_id, coin_id, target_price, above=True,
                                interval_minutes=1.0, is_symbol=False, note=""):
        """Create an alert respecting autostart; return without awaiting its loop."""
        if not self.add_task(loop_id, coin_id, target_price, above, interval_minutes, note, is_symbol):
            return False
        await self.reconcile_tasks()
        return True

    async def get_price_geko(self, coin_id: str, vs_currency=None, timeout_input=10.0, symbol=True):
        coin_id = coin_id.lower().strip()
        currency = vs_currency or ("usd" if self.currency.upper() == "USDT" else self.currency.lower())
        lookup = "symbols" if symbol else "ids"
        params = {lookup: coin_id, "vs_currencies": currency}
        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_input) as client:
                response = await client.get("https://api.coingecko.com/api/v3/simple/price", params=params)
                response.raise_for_status()
                prices = response.json()
                quote = prices.get(coin_id) if isinstance(prices, dict) else None
                if not isinstance(quote, dict) or quote.get(currency) is None:
                    logger.warning("PRICE_UNAVAILABLE coin=%r lookup=%s currency=%s; check CoinGecko ID and currency code",
                                   coin_id, lookup, currency)
                    return None
                price = float(quote[currency])
                if not math.isfinite(price) or price < 0:
                    raise ValueError("Invalid price")
                logger.info("PRICE_FETCHED coin=%r lookup=%s currency=%s price=%s elapsed_ms=%.0f",
                            coin_id, lookup, currency.upper(), price, (perf_counter() - started) * 1000)
                return prices
        except httpx.HTTPStatusError as error:
            hint = "rate limit reached; increase alert intervals" if error.response.status_code == 429 else "check CoinGecko availability and request parameters"
            logger.warning("PRICE_HTTP_ERROR coin=%r status=%s elapsed_ms=%.0f; %s",
                           coin_id, error.response.status_code, (perf_counter() - started) * 1000, hint)
        except httpx.RequestError as error:
            logger.warning("PRICE_NETWORK_ERROR coin=%r %s timeout_seconds=%s elapsed_ms=%.0f; check internet, DNS and HTTPS access",
                           coin_id, error_context(error), timeout_input, (perf_counter() - started) * 1000)
        except (ValueError, TypeError) as error:
            logger.warning("PRICE_RESPONSE_INVALID coin=%r %s; CoinGecko returned an invalid price or JSON",
                           coin_id, error_context(error))
        return None

    async def _run_alert(self, task_id):
        delivered_to = set()
        previous_condition = None
        no_recipients_logged = False
        while not self._closed:
            try:
                config = self._read_config()
                task = config.get("tasks", {}).get(task_id)
                if task is None or task.get("is_running") != 1:
                    return
                self._validate_task(task)
                coin = task["symbol"].lower().strip()
                currency = "usd" if self.currency.upper() == "USDT" else self.currency.lower()
                condition = (coin, task["price"], task["is_above"], task.get("is_symbol", 1))
                if condition != previous_condition:
                    delivered_to.clear()
                    previous_condition = condition
                prices = await self.get_price_geko(coin, symbol=bool(task.get("is_symbol", 1)))
                if prices is None:
                    logger.warning("ALERT_RETRY id=%r retry_seconds=%s", task_id, self.retry_seconds)
                    await asyncio.sleep(self.retry_seconds)
                    continue
                current_price = float(prices[coin][currency])
                if not math.isfinite(current_price):
                    raise ValueError("Некорректная цена")
                # Recheck after network I/O: End alert must not send a late notification.
                config = self._read_config()
                latest = config.get("tasks", {}).get(task_id)
                if latest is None or latest.get("is_running") != 1:
                    return
                if latest != task:
                    continue
                target = float(task["price"])
                met = current_price >= target if task["is_above"] else current_price <= target
                logger.info("PRICE_CHECK id=%r coin=%r price=%s currency=%s condition=%s target=%s condition_met=%s interval_seconds=%s",
                            task_id, coin, current_price, currency.upper(), ">=" if task["is_above"] else "<=",
                            target, met, float(task["time"]) * 60)
                recipients = set(config.get("main", {}).get("ADMINS", []))
                if not recipients and not no_recipients_logged:
                    logger.warning("ALERT_NO_RECIPIENTS id=%r; tracking continues; configure ADMINS or register with PASSWORD", task_id)
                    no_recipients_logged = True
                elif recipients:
                    no_recipients_logged = False
                pending = recipients - delivered_to
                if met and pending:
                    direction = "≥" if task["is_above"] else "≤"
                    lang = self.get_language()
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                        [button(lang, "stop_id", "stop_by_id")],
                        [button(lang, "alerts", "alerts")],
                    ])
                    text = t(lang, "alert_hit", coin=coin.upper(), price=f"{current_price:g}",
                             currency=currency.upper(), direction=direction, target=f"{target:g}", id=task_id)
                    note = str(task.get("note") or "").strip()
                    if note and note not in ("note", "No note"):
                        text += "\n\n" + t(lang, "note", note=note[:500])
                    text += "\n\n" + t(lang, "tracking_continues")
                    logger.info("ALERT_TRIGGERED id=%r price=%s target=%s recipients=%s pending=%s", task_id, current_price, target, len(recipients), len(pending))
                    for admin_id in sorted(pending):
                        if await send_message(self.bot, admin_id, text, reply_markup=markup):
                            delivered_to.add(admin_id)
                    logger.info("ALERT_DELIVERY id=%r delivered=%s total=%s pending=%s",
                                task_id, len(recipients & delivered_to), len(recipients), len(recipients - delivered_to))
                    if recipients - delivered_to:
                        logger.warning("ALERT_DELIVERY_RETRY id=%r pending=%s retry_seconds=%s",
                                       task_id, len(recipients - delivered_to), self.retry_seconds)
                        await asyncio.sleep(self.retry_seconds)
                        continue
                if not met:
                    delivered_to.clear()
                await asyncio.sleep(float(task["time"]) * 60)
            except (OSError, ValueError, KeyError, TypeError) as error:
                logger.warning("ALERT_CHECK_FAILED id=%r %s retry_seconds=%s; check coin ID and configuration", task_id, error_context(error), self.retry_seconds)
                await asyncio.sleep(self.retry_seconds)
            except Exception as error:
                logger.error("ALERT_CHECK_FAILED id=%r %s retry_seconds=%s", task_id, error_context(error), self.retry_seconds)
                await asyncio.sleep(self.retry_seconds)

    def stop_task(self, test_id):
        data = self._read_config()
        if test_id not in data.get("tasks", {}):
            return False
        data["tasks"][test_id]["is_running"] = 0
        if not self._write_config(data):
            return False
        self._cancel_worker(test_id)
        logger.info("ALERT_DISABLED id=%r", test_id)
        return True

    async def stop_all_tasks(self):
        data = self._read_config()
        count = sum(task.get("is_running") == 1 for task in data.get("tasks", {}).values())
        for task in data.get("tasks", {}).values():
            task["is_running"] = 0
        if not self._write_config(data):
            raise OSError("Не удалось сохранить остановку алертов")
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        # Do not remove any new workers started by another handler in the meantime.
        self._workers = {key: task for key, task in self._workers.items() if not task.done()}
        logger.info("ALERTS_DISABLED count=%s", count)
        return count

    def delete_task(self, test_id):
        data = self._read_config()
        if test_id not in data.get("tasks", {}):
            return False
        del data["tasks"][test_id]
        if not self._write_config(data):
            return False
        self._cancel_worker(test_id)
        logger.info("ALERT_DELETED id=%r", test_id)
        return True

    def delete_inactive_tasks(self):
        data = self._read_config()
        data["tasks"] = {key: task for key, task in data.get("tasks", {}).items() if task.get("is_running") != 0}
        if not self._write_config(data):
            return False
        for key in self._workers:
            if key not in data["tasks"]:
                self._cancel_worker(key)
        return True

    def clear_all_tasks(self):
        data = self._read_config()
        count = len(data.get("tasks", {}))
        data["tasks"] = {}
        if not self._write_config(data):
            return False
        for key in self._workers:
            self._cancel_worker(key)
        logger.info("ALERTS_CLEARED count=%s", count)
        return True

    def toggle_task_status(self, test_id):
        data = self._read_config()
        task = data.get("tasks", {}).get(test_id)
        if task is None:
            return False
        task["is_running"] = 0 if task.get("is_running") == 1 else 1
        if not self._write_config(data):
            return False
        if not task["is_running"]:
            self._cancel_worker(test_id)
        return True

    async def update_task_param(self, task_id, param_name, new_value):
        data = self._read_config()
        task = data.get("tasks", {}).get(task_id)
        if task is None or param_name not in task:
            return False
        task[param_name] = new_value
        try:
            self._validate_task(task)
        except (KeyError, TypeError, ValueError):
            return False
        if not self._write_config(data):
            return False
        await self.reconcile_tasks()
        return True
