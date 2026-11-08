from html import escape
from math import ceil
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgbot.i18n import t
from tgbot.keyboards.inline import button

PAGE_SIZE = 4


def alert_page(tasks, page=0, currency="USDT", lang="ru"):
    items = list(tasks.items())
    pages = max(1, ceil(len(items) / PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    running = sum(task.get("is_running") == 1 for _, task in items)
    currency = "USD" if currency.upper() == "USDT" else currency.upper()
    lines = [t(lang, "list_title"), t(lang, "list_counts", total=len(items), running=running)]
    if not items:
        lines.append("\n" + t(lang, "empty"))
    for task_id, task in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        status = t(lang, "enabled" if task.get("is_running") == 1 else "disabled")
        direction = "≥" if task.get("is_above") else "≤"
        lines.extend([
            f"\n<b>{escape(str(task.get('symbol', '?')).upper()[:60])}</b> · {status}",
            f"ID: <code>{escape(task_id[:64])}</code>",
            t(lang, "target", direction=direction, price=str(task.get("price", "?"))[:30], currency=currency),
            t(lang, "interval", minutes=str(task.get("time", "?"))[:30]),
        ])
        note = str(task.get("note") or "")
        if note and note not in ("note", "No note"):
            lines.append(t(lang, "note", note=note[:180]))
    lines.append("\n" + t(lang, "page", page=page + 1, pages=pages))
    navigation = []
    if page > 0:
        navigation.append(button(lang, "back", f"alerts:{page - 1}"))
    navigation.append(InlineKeyboardButton(text=f"↻ {page + 1}/{pages}", callback_data=f"alerts:{page}"))
    if page + 1 < pages:
        navigation.append(button(lang, "next", f"alerts:{page + 1}"))
    rows = [navigation, [button(lang, "create", "add_alert")]]
    if items:
        rows.extend([
            [button(lang, "start_id", "start_by_id"), button(lang, "stop_id", "stop_by_id")],
            [button(lang, "delete_id", "delete_by_id"), button(lang, "delete_all", "clear_alerts")],
            [button(lang, "stop_all", "end_alert")],
        ])
    rows.append([button(lang, "home", "menu")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)
