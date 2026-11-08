# CryptoTracker · 1.0

**Written in Python 3.10+**: `aiogram 3` handles the Telegram bot, `httpx` sends requests to CoinGecko, and `asyncio` runs background tasks. Settings and alerts are stored in JSON. No database or separate web server is required.

**Language:** [Русский](README.md) · English

[Read the CryptoTracker announcement on my Telegram channel](https://t.me/freecod1ng/128)

## What it is

A Telegram bot for tracking cryptocurrency prices through CoinGecko. Create alerts, set a target price and check interval, and receive notifications in Telegram. The interface supports Russian and English.

The bot **does not trade**, connect to wallets, or require exchange API keys. It tracks prices and sends notifications.

## How it works

Run the application on your computer or server and control it through your own Telegram bot. For example, create an alert saying “notify me when Bitcoin is ≥ 100,000 USD,” choose a five-minute check interval, and add a note. The bot periodically requests the price from CoinGecko and sends a message when the condition is met.

Each alert runs in the background. After a notification, tracking continues, but another notification is sent only when the price crosses the threshold again. Enabled alerts are restored from `cfg.json` when the application restarts. Prices are not checked while the application is offline.

## Features

- Look up prices by symbol (`btc`) or CoinGecko ID (`bitcoin`).
- Create alerts step by step: unique ID, coin, target price, condition `≥` / `≤`, interval in minutes, and note.
- Track multiple coins in the background while keeping the menu responsive.
- Save alerts in `cfg.json` and restore enabled alerts after a restart.
- Browse alert cards with pagination: four per page.
- Start an alert by ID without creating duplicate tracking loops.
- **End alert by ID**: stop one alert while keeping its record.
- **Stop all alerts**: disable all alerts without deleting them.
- Delete an alert by ID or clear the entire alert list. Bot settings are preserved.
- Choose whether new alerts are disabled or start immediately.
- Switch languages in **Settings → Русский / English**. The language is shared by all administrators, persists after a restart, and applies to new messages, buttons, and notifications.
- Administrator-only management, with optional password-based registration.

## Quick installation

You need **Python 3.10+**, Git, and internet access to Telegram and CoinGecko. Verified on Python 3.14. On Windows, enable **Add python.exe to PATH** when installing Python. Dependencies are listed in `req.txt`; `requirements.txt` references it.

### 1. Download and install

Copy the block for your operating system into a terminal. You do not need to activate the virtual environment: the commands use its Python directly. An existing `cfg.json` will not be overwritten.

**Linux / macOS:**

```bash
git clone https://github.com/miusGG/CryptoTracker.git
cd CryptoTracker
python3 -m venv .venv
.venv/bin/python -m pip install -r req.txt
test -f cfg.json || cp cfg_example.json cfg.json
```

**Windows — PowerShell:**

```powershell
git clone https://github.com/miusGG/CryptoTracker.git
cd CryptoTracker
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r req.txt
if (!(Test-Path cfg.json)) { Copy-Item cfg_example.json cfg.json }
```

Without Git: select **Code → Download ZIP** on the repository page, extract the archive, open a terminal in the folder containing `bot.py`, and run the commands for your system starting with the creation of `.venv`.

### 2. Fill in two fields

Open `cfg.json` in a text editor:

- `BOT_TOKEN`: create a bot by sending `/newbot` to **@BotFather** in Telegram. Replace `PASTE_TELEGRAM_BOT_TOKEN_HERE` with the token you receive, keeping the quotation marks.
- `ADMINS`: replace `123456789` with your numeric Telegram user ID, for example `[987654321]`. Use your account's ID, not your `@username` or the new bot's ID.

You can leave the other fields as they are: Russian language, USD, new alerts disabled, and password-based registration disabled. To start in English, set `language` to `en`. You can also change the language and autostart setting through the bot's menu.

### 3. Start the bot

Open your bot in Telegram and press **Start**. From the project folder, run:

```bash
# Linux / macOS
.venv/bin/python bot.py
```

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe bot.py
```

Wait for `BOT_READY` in the console, then send `/menu` to the bot. Create your first alert. By default, you need to enable it using **My alerts → Start by ID** after creating it. To start new alerts automatically, enable that option in **Settings**.

For subsequent launches, use the same command from step 3. Keep the terminal open while the bot is running. Press `Ctrl+C` to stop it.

**Troubleshooting installation:**

- `python3` / `py` not found: install Python 3.10+ and open a new terminal. If only `python` is available on Windows, use it instead of `py -3`.
- On Ubuntu/Debian, environment creation fails with a message mentioning `venv` or `ensurepip`: run `sudo apt install python3-venv`, then create `.venv` again.
- `ModuleNotFoundError`: reinstall dependencies using the command from step 1 and make sure you launch the Python executable inside `.venv`.
- `CONFIG_MISSING` / `CONFIG_INVALID`: check that `cfg.json` exists next to `bot.py` and that the two fields from step 2 are filled in correctly.
- `BOT_FAILED stage=telegram_auth`: check your token and access to Telegram. Do not run a second instance with the same token.

## Settings

The `cfg_example.json` template contains no real token or active alerts:

```json
{
  "main": {
    "BOT_TOKEN": "PASTE_TELEGRAM_BOT_TOKEN_HERE",
    "PASSWORD": "",
    "ADMINS": [123456789],
    "currency": "USD",
    "autostart": false,
    "language": "ru"
  },
  "tasks": {}
}
```

| Field | Purpose |
| --- | --- |
| `BOT_TOKEN` | Your Telegram bot token from @BotFather. |
| `PASSWORD` | Optional password: a user who sends it to the bot gains administrator access. An empty string disables password-based registration. |
| `ADMINS` | List of administrators' Telegram user IDs. Each receives notifications and can manage the shared alert list. |
| `currency` | CoinGecko quote currency, such as `USD`, `EUR`, or `BTC`. For compatibility, `USDT` is requested as `USD`; this is not an exchange quote for a USDT trading pair. Changes take effect after a restart. |
| `autostart` | `false` / `0`: new alerts are disabled; `true` / `1`: new alerts start immediately. Can be changed using menu buttons. |
| `language` | `ru` or `en`. Can be changed using menu buttons. Older configs without this field default to Russian. |
| `tasks` | Saved alerts. The bot updates this section automatically. |

For personal use, leave `PASSWORD` empty and put your ID in `ADMINS`. Keep your working `cfg.json` private; it is excluded by `.gitignore`.

## How alerts behave

1. Select **Create alert** and complete the six steps. Use a CoinGecko ID for an unambiguous coin selection: multiple coins can share a symbol.
2. If autostart is disabled, select **My alerts → Start by ID**.
3. The first price check runs immediately; later checks follow your chosen interval. Fractional minutes are supported: `0.5` = 30 seconds.
4. When the condition is met, you receive a message containing the current price, target condition, alert ID, and your note.
5. Tracking continues. Another notification is sent after the price leaves the matching condition and enters it again. An unchanged condition does not produce a message on every check. The condition is evaluated afresh after a restart.

If Telegram delivery fails, the bot retries after 60 seconds while the condition remains met. For Telegram rate limits, Telegram specifies the waiting time. Administrators who already received the notification do not receive the retry. An administrator added during tracking receives a notification on the next check that meets the condition. Delivery history is kept in memory and resets after a restart.

`is_running` is the **saved intent to track an alert**, not a guarantee of a successful API response. A value of `1` restores its tracking loop when the bot starts; `0` leaves it disabled. Flag changes made directly in JSON are picked up approximately once per second.

| Action in My alerts | Result |
| --- | --- |
| Start by ID | Sets `is_running = 1`; one background loop runs for that ID. |
| End alert by ID | Sets `is_running = 0` for the selected alert only; its record is kept. |
| Stop all alerts | Sets `is_running = 0` for every record. |
| Delete by ID | Removes the record entirely and cancels its loop. |
| Delete all alerts | Sets `tasks` to `{}` and cancels the loops. |

Stopping or deleting an alert interrupts the wait for its next check and any request in progress. Messages already sent remain in the chat. **Delete all alerts** clears the list immediately.

Example record inside `tasks` (you do not need to add it manually):

```json
"btc-watch": {
  "is_symbol": 0,
  "symbol": "bitcoin",
  "price": 100000,
  "is_above": 1,
  "time": 5,
  "is_running": 1,
  "note": "Check the price movement"
}
```

`is_symbol`: `1` means symbol, `0` means CoinGecko ID. `is_above`: `1` means price ≥ target, `0` means price ≤ target. `time` is measured in minutes. Each ID must be unique. Notes can contain up to 500 characters.

## Commands

| Command | Action |
| --- | --- |
| `/start` | Greeting or administrator's main menu. |
| `/menu` | Main menu. |
| `/cancel` | Cancel the current input and return to the menu. |
| `/price s btc` | Current price by symbol. |
| `/price n bitcoin` | Current price by CoinGecko ID. |

After updating the code, send a new `/menu`: buttons in previously sent messages are not redrawn automatically.

## Console output

Logs are written to standard error (`stderr`) in this format:

```text
date time | level | module | EVENT parameters
```

Event names are always in English for easy searching, regardless of the Telegram interface language. Timestamps use the operating system's local time. Example with fictional values:

```text
2026-11-08 12:00:00 | INFO    | __main__ | BOT_STARTING version=1.0 python=3.14.0 config=/path/CryptoTracker/cfg.json
2026-11-08 12:00:00 | INFO    | __main__ | TELEGRAM_CONNECTED bot_id=123456 username=@example_bot
2026-11-08 12:00:00 | INFO    | __main__ | CONFIG_LOADED currency=USD language=en autostart=0 admins=1 alerts=3
2026-11-08 12:00:00 | INFO    | crypto | ALERT_STARTED id='btc-watch' coin='bitcoin' lookup=id condition=>= target=100000 currency=USD interval_min=5
2026-11-08 12:00:00 | INFO    | crypto | ALERTS_RESTORED total=3 enabled=1 running=1 disabled=2 invalid=0
2026-11-08 12:00:01 | INFO    | __main__ | BOT_READY polling=true language=en admins=1; open Telegram /menu; Ctrl+C to stop
2026-11-08 12:00:01 | INFO    | crypto | PRICE_FETCHED coin='bitcoin' lookup=ids currency=USD price=100100.0 elapsed_ms=240
2026-11-08 12:00:01 | INFO    | crypto | PRICE_CHECK id='btc-watch' coin='bitcoin' price=100100.0 currency=USD condition=>= target=100000.0 condition_met=True interval_seconds=300.0
2026-11-08 12:00:01 | INFO    | crypto | ALERT_TRIGGERED id='btc-watch' price=100100.0 target=100000.0 recipients=1 pending=1
2026-11-08 12:00:01 | INFO    | tgbot.services.broadcaster | TELEGRAM_SENT user_id=123456789
2026-11-08 12:00:01 | INFO    | crypto | ALERT_DELIVERY id='btc-watch' delivered=1 total=1 pending=0
2026-11-08 12:01:00 | INFO    | crypto | ALERT_DISABLED id='btc-watch'
```

| Event | Meaning / what to do |
| --- | --- |
| `BOT_STARTING`, `BOT_READY` | Starting up and ready to receive commands. |
| `TELEGRAM_CONNECTED` | Telegram accepted the token; shows the connected bot's ID and username. |
| `CONFIG_LOADED` | Currency, language, autostart, administrator count, and saved alert count. |
| `ALERTS_RESTORED` | Counts of saved, enabled, running, disabled, and invalid alerts. |
| `ALERT_CREATED`, `ALERT_STARTED` | A record was created / tracking actually started. |
| `PRICE_FETCHED` | Coin, symbol/ID lookup, currency, price, and API response time in milliseconds. Also logged for price checks through the menu. |
| `PRICE_CHECK` | Alert ID, coin, price, currency, comparison operator, target, result, and normal check interval. |
| `ALERT_TRIGGERED`, `TELEGRAM_SENT` | The condition was met / a message was delivered to Telegram. |
| `ALERT_DELIVERY`, `ALERT_DELIVERY_RETRY` | How many administrators received the notification, how many still need it, and the retry delay. |
| `ALERT_DISABLED`, `ALERTS_DISABLED` | One alert / all alerts stopped. |
| `ALERT_DELETED`, `ALERTS_CLEARED` | One record / all records deleted. |
| `BOT_STOPPING`, `WORKER_STOPPED`, `ALERT_SERVICE_CLOSED`, `BOT_STOPPED` | Tasks and the bot are shutting down; saved flags are preserved for the next start. |
| `LANGUAGE_CHANGED`, `AUTOSTART_CHANGED`, `ADMIN_ADDED` | A setting changed or an administrator registered. |
| `CONFIG_MISSING` | Copy `cfg_example.json` to `cfg.json`. |
| `CONFIG_INVALID`, `CONFIG_INVALID_JSON` | Check the indicated fields or JSON line and column. |
| `CONFIG_SAVE_FAILED` | Check write permissions and free disk space. |
| `CONFIG_RELOAD_FAILED` | Could not reload the modified JSON; shows the error and retry delay. |
| `ALERT_INVALID`, `ALERT_CHECK_FAILED` | Check the CoinGecko ID, price, interval, and record format. |
| `PRICE_HTTP_ERROR status=429` | CoinGecko rate limit reached; increase check intervals. |
| `PRICE_NETWORK_ERROR`, `ALERT_RETRY` | Network unavailable / price check will retry after 60 seconds. |
| `PRICE_UNAVAILABLE`, `PRICE_RESPONSE_INVALID` | CoinGecko returned no price for the coin/currency, or returned invalid data. |
| `TELEGRAM_FORBIDDEN` | Open the bot chat and press Start, or unblock the bot. |
| `TELEGRAM_SEND_FAILED`, `TELEGRAM_BAD_REQUEST` | Delivery failed; check connectivity and recipient ID. |
| `TELEGRAM_RATE_LIMIT` | Telegram limited sending; the bot waits the specified number of seconds and retries. |
| `NO_ADMINS`, `ALERT_NO_RECIPIENTS` | No notification recipients. Fill in ADMINS or register with PASSWORD. |
| `BOT_FAILED`, `HANDLER_FAILED`, `WORKER_FAILED` | Error type, file, line, and function. Startup errors include the stage; handler errors include the update ID and type. |

For example, `BOT_FAILED stage=telegram_auth error=TelegramUnauthorizedError` means Telegram rejected the token. `stage=restore_alerts` refers to restoring alerts, `stage=startup_notifications` to sending the startup message, and `stage=polling` to receiving updates. `source=crypto.py:123 function=_run_alert` helps locate the failure without printing secret data.

Levels: `INFO` means normal operation, `WARNING` means a temporary problem or something requiring attention, and `ERROR` means an action failed. Normal logs do not print the token, password, complete config, or note text. Alert IDs, coins, and recipient IDs are logged.

To view and save logs at the same time:

```bash
# Linux / macOS
.venv/bin/python bot.py 2>&1 | tee bot.log
```

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe bot.py 2>&1 | Tee-Object bot.log
```

## Limitations

- Checks run while `bot.py` is running and the network is available. Closing the terminal or shutting down the computer stops checks. OS startup integration / a systemd service is not included.
- Run one bot instance per config. Multiple processes sharing the same JSON file are not supported.
- Check intervals and the number of alerts affect CoinGecko rate limits; the free API may temporarily reject requests. After an error, checks retry after 60 seconds.
- Prices come from CoinGecko, not a real-time stream of exchange trades. The `exchange` field in older configs does not select an exchange.
- The alert list and language are shared by all administrators. This bot is designed for personal or team use, without separate user accounts.

## Project structure

```text
bot.py                    startup, polling, shutdown, and logs
crypto.py                 CoinGecko, background tasks, config persistence
tgbot/handlers/           Telegram commands and buttons
tgbot/keyboards/          keyboards
tgbot/i18n.py             Russian and English text
tgbot/services/           alert cards and message delivery
cfg_example.json          configuration template without secrets
req.txt                   dependencies
```
