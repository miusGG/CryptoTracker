from tgbot.i18n import t
import logging
import math
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from crypto import CoinGekoCryptoService
from tgbot.filters.admin import AdminFilter
from tgbot.keyboards.reply import above_below_keyboard as abk
from tgbot.keyboards.inline import menu_keyboard as mk, settings_keyboard as sk
from tgbot.keyboards.inline import symbol_is_keyboard as sik
from tgbot.keyboards.inline import symbol_is_for_check_price as sifcp
from tgbot.keyboards.inline import back_to_alerts_keyboard
from tgbot.services.alert_views import alert_page
logger = logging.getLogger(__name__)
admin_router = Router()
admin_router.message.filter(AdminFilter())
admin_router.callback_query.filter(AdminFilter())

class AddAlertForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_symbol = State()
    waiting_for_price = State()
    waiting_for_above = State()
    waiting_for_time = State()
    waiting_for_note = State()

class CheckPriceForm(StatesGroup):
    waiting_for_coin = State()

class StartById(StatesGroup):
    waiting_for_id = State()

class DeleteById(StatesGroup):
    waiting_for_id = State()

async def edit_view(callback, text, keyboard):
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as error:
        if 'message is not modified' not in str(error):
            raise

def settings_text(enabled, lang='ru'):
    return t(lang, 'settings', status=t(lang, 'on_default' if enabled else 'off_default'))

@admin_router.message(CommandStart())
async def admin_start(message: Message, state: FSMContext, lang='ru'):
    await state.clear()
    await message.answer(t(lang, 'menu'), reply_markup=mk(lang=lang))

@admin_router.message(Command('menu', 'cancel'))
async def main_menu(message: Message, state: FSMContext, lang='ru'):
    await state.clear()
    await message.answer(t(lang, 'choose'), reply_markup=ReplyKeyboardRemove())
    await message.answer(t(lang, 'menu'), reply_markup=mk(lang=lang))

@admin_router.callback_query(F.data == 'menu')
async def menu_callback(callback: CallbackQuery, state: FSMContext, lang='ru'):
    await state.clear()
    await callback.answer()
    await edit_view(callback, t(lang, 'menu'), mk(lang=lang))

@admin_router.callback_query(F.data == 'settings')
async def settings_callback(callback: CallbackQuery, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    await state.clear()
    enabled = crypt.get_autostart()
    await callback.answer()
    await edit_view(callback, settings_text(enabled, lang=lang), sk(enabled, lang=lang))

@admin_router.callback_query(F.data.in_({'autostart:0', 'autostart:1'}))
async def autostart_callback(callback: CallbackQuery, crypt: CoinGekoCryptoService, lang='ru'):
    enabled = callback.data == 'autostart:1'
    if not crypt.set_autostart(enabled):
        await callback.answer(t(lang, 'save_error'), show_alert=True)
        return
    await callback.answer(t(lang, 'saved'))
    await edit_view(callback, settings_text(enabled, lang=lang), sk(enabled, lang=lang))

@admin_router.callback_query((F.data == 'alerts') | F.data.startswith('alerts:'))
async def alerts_menu_callback(callback: CallbackQuery, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    await state.clear()
    try:
        page = int(callback.data.split(':', 1)[1]) if ':' in callback.data else 0
    except ValueError:
        page = 0
    text, keyboard = alert_page(crypt.list_tasks(), page, crypt.currency, lang=lang)
    await callback.answer()
    await edit_view(callback, text, keyboard)

@admin_router.callback_query(F.data == 'end_alert')
async def end_alert_callback(callback: CallbackQuery, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    await callback.answer()
    await state.clear()
    try:
        count = await crypt.stop_all_tasks()
    except (OSError, ValueError):
        logger.error('STOP_ALL_FAILED; check cfg.json permissions')
        await callback.message.answer(t(lang, 'stop_all_error'))
        return
    await callback.message.answer(t(lang, 'stop_all_done', count=count), reply_markup=mk(lang=lang))

@admin_router.callback_query(F.data.startswith('delete_alert:'))
async def process_delete_alert(callback: CallbackQuery, lang='ru'):
    await callback.answer(t(lang, 'hidden'))
    await callback.message.delete()

@admin_router.callback_query(F.data == 'delete_by_id')
async def delete_by_id_prompt(callback: CallbackQuery, state: FSMContext, lang='ru'):
    await state.clear()
    await state.set_state(DeleteById.waiting_for_id)
    await callback.answer()
    await callback.message.answer(t(lang, 'delete_prompt'), reply_markup=back_to_alerts_keyboard(lang=lang))

@admin_router.message(DeleteById.waiting_for_id)
async def delete_by_id_submit(mes: Message, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    task_id = (mes.text or '').strip()
    try:
        if task_id not in crypt.list_tasks():
            await mes.answer(t(lang, 'not_found'), reply_markup=back_to_alerts_keyboard(lang=lang))
            return
        if not crypt.delete_task(task_id):
            raise OSError('Не удалось сохранить удаление')
    except (OSError, ValueError):
        logger.error('DELETE_ALERT_FAILED; check cfg.json permissions')
        await mes.answer(t(lang, 'delete_error'), reply_markup=back_to_alerts_keyboard(lang=lang))
        return
    await state.clear()
    await mes.answer(t(lang, 'delete_done', id=task_id), reply_markup=back_to_alerts_keyboard(lang=lang))

@admin_router.callback_query(F.data == 'clear_alerts')
async def clear_alerts_callback(callback: CallbackQuery, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    try:
        if not crypt.clear_all_tasks():
            raise OSError('Не удалось сохранить очистку')
    except (OSError, ValueError):
        logger.error('CLEAR_ALERTS_FAILED; check cfg.json permissions')
        await callback.answer(t(lang, 'clear_error'), show_alert=True)
        return
    await state.clear()
    await callback.answer(t(lang, 'clear_done'))
    text, keyboard = alert_page(crypt.list_tasks(), currency=crypt.currency, lang=lang)
    await edit_view(callback, text, keyboard)

@admin_router.callback_query(F.data == 'add_alert')
async def add_alert_callback(callback: CallbackQuery, state: FSMContext, lang='ru'):
    await state.clear()
    await callback.answer()
    await callback.message.answer(t(lang, 'new_prompt'), reply_markup=sik(lang=lang))

@admin_router.callback_query(F.data.in_({'is_symbol', 'is_name'}))
async def add_alert_type(callback: CallbackQuery, state: FSMContext, lang='ru'):
    await state.clear()
    await state.update_data(symbol=callback.data == 'is_symbol')
    await state.set_state(AddAlertForm.waiting_for_name)
    await callback.answer()
    await callback.message.answer(t(lang, 'name_prompt'))

@admin_router.message(AddAlertForm.waiting_for_name)
async def add_alert_name(mes: Message, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    name = (mes.text or '').strip()
    if not name or len(name) > 64:
        await mes.answer(t(lang, 'name_error'))
        return
    if name in crypt.list_tasks():
        await mes.answer(t(lang, 'name_exists'))
        return
    await state.update_data(name=name)
    await state.set_state(AddAlertForm.waiting_for_symbol)
    await mes.answer(t(lang, 'coin_prompt'))

@admin_router.message(AddAlertForm.waiting_for_symbol)
async def add_alert_coin(mes: Message, state: FSMContext, lang='ru'):
    coin = (mes.text or '').lower().strip()
    if not coin or len(coin) > 100 or any((char.isspace() or char == ',' for char in coin)):
        await mes.answer(t(lang, 'coin_error'))
        return
    await state.update_data(coin=coin)
    await state.set_state(AddAlertForm.waiting_for_price)
    await mes.answer(t(lang, 'target_prompt'))

def positive_number(text):
    value = float((text or '').replace(',', '.'))
    if not math.isfinite(value) or value <= 0:
        raise ValueError
    return value

@admin_router.message(AddAlertForm.waiting_for_price)
async def add_alert_price(mes: Message, state: FSMContext, lang='ru'):
    try:
        price = positive_number(mes.text)
    except ValueError:
        await mes.answer(t(lang, 'target_error'))
        return
    await state.update_data(price=price)
    await state.set_state(AddAlertForm.waiting_for_above)
    await mes.answer(t(lang, 'direction_prompt'), reply_markup=abk(lang=lang))

@admin_router.message(AddAlertForm.waiting_for_above)
async def add_alert_above(mes: Message, state: FSMContext, lang='ru'):
    directions = {'Above': True, 'Below': False, **{t(code, key): value for code in ('ru', 'en') for key, value in (('above', True), ('below', False))}}
    if mes.text not in directions:
        await mes.answer(t(lang, 'direction_error'), reply_markup=abk(lang=lang))
        return
    await state.update_data(above=directions[mes.text])
    await state.set_state(AddAlertForm.waiting_for_time)
    await mes.answer(t(lang, 'interval_prompt'), reply_markup=ReplyKeyboardRemove())

@admin_router.message(AddAlertForm.waiting_for_time)
async def add_alert_time(mes: Message, state: FSMContext, lang='ru'):
    try:
        interval = positive_number(mes.text)
    except ValueError:
        await mes.answer(t(lang, 'interval_error'))
        return
    await state.update_data(time=interval)
    await state.set_state(AddAlertForm.waiting_for_note)
    await mes.answer(t(lang, 'note_prompt'))

@admin_router.message(AddAlertForm.waiting_for_note)
async def add_alert_note(mes: Message, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    if mes.text is None or len(mes.text) > 500:
        await mes.answer(t(lang, 'note_error'))
        return
    data = await state.get_data()
    note = '' if mes.text.strip() in ('-', 'note') else mes.text.strip()
    try:
        created = await crypt.start_price_alert(loop_id=data['name'], coin_id=data['coin'], target_price=data['price'], above=data['above'], interval_minutes=data['time'], is_symbol=data['symbol'], note=note)
    except (OSError, ValueError):
        logger.error('CREATE_ALERT_FAILED; check cfg.json and input')
        await mes.answer(t(lang, 'create_error'))
        return
    if not created:
        await mes.answer(t(lang, 'create_conflict'))
        await state.clear()
        return
    await state.clear()
    running = crypt.get_task_running_status(data['name']) == 1
    status = t(lang, 'created_on') if running else t(lang, 'created_off')
    await mes.answer(t(lang, 'created', id=data['name']) + '\n' + status, reply_markup=mk(lang=lang))

@admin_router.callback_query(F.data == 'start_by_id')
async def start_by_id_step1(callback: CallbackQuery, state: FSMContext, lang='ru'):
    await state.clear()
    await state.set_state(StartById.waiting_for_id)
    await callback.answer()
    await callback.message.answer(t(lang, 'start_prompt'))

@admin_router.message(StartById.waiting_for_id)
async def start_by_id_step2(mes: Message, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    search_id = (mes.text or '').strip()
    already_running = crypt.get_task_running_status(search_id) == 1
    if not await crypt.start_price_alert_by_id(search_id):
        await mes.answer(t(lang, 'start_error'))
        return
    await state.clear()
    await mes.answer(t(lang, 'already_started' if already_running else 'started', id=search_id), reply_markup=mk(lang=lang))

@admin_router.callback_query(F.data == 'indicators')
async def indicators_callback(callback: CallbackQuery, lang='ru'):
    await callback.answer(t(lang, 'indicators'), show_alert=True)

@admin_router.callback_query(F.data == 'check_price')
async def check_price_callback(callback: CallbackQuery, state: FSMContext, lang='ru'):
    await state.clear()
    await callback.answer()
    await callback.message.answer(t(lang, 'price_prompt'), reply_markup=sifcp(lang=lang))

@admin_router.callback_query(F.data.in_({'is_symbol_check_price', 'is_name_check_price'}))
async def price_type_callback(callback: CallbackQuery, state: FSMContext, lang='ru'):
    await state.clear()
    await state.update_data(symbol=callback.data == 'is_symbol_check_price')
    await state.set_state(CheckPriceForm.waiting_for_coin)
    await callback.answer()
    await callback.message.answer(t(lang, 'price_coin_prompt'))

async def price_text(crypt, coin, symbol, lang='ru'):
    prices = await crypt.get_price_geko(coin_id=coin, symbol=symbol)
    currency = 'usd' if crypt.currency.upper() == 'USDT' else crypt.currency.lower()
    try:
        price = float(prices[coin][currency])
        if not math.isfinite(price) or price < 0:
            raise ValueError
    except (TypeError, KeyError, ValueError):
        return t(lang, 'price_error')
    return t(lang, 'price_result', coin=coin.upper()[:100], price=f'{price:g}', currency=currency.upper())

@admin_router.message(Command('price'))
async def check_price_command(mes: Message, command: CommandObject, crypt: CoinGekoCryptoService, lang='ru'):
    parts = (command.args or '').split()
    if len(parts) != 2 or parts[0].lower() not in ('s', 'n'):
        await mes.answer(t(lang, 'price_usage'))
        return
    await mes.answer(await price_text(crypt, parts[1].lower(), parts[0].lower() == 's', lang=lang), reply_markup=mk(lang=lang))

@admin_router.message(CheckPriceForm.waiting_for_coin)
async def check_price(mes: Message, state: FSMContext, crypt: CoinGekoCryptoService, lang='ru'):
    coin = (mes.text or '').lower().strip()
    if not coin:
        await mes.answer(t(lang, 'text_coin'))
        return
    data = await state.get_data()
    await mes.answer(await price_text(crypt, coin, data['symbol'], lang=lang), reply_markup=mk(lang=lang))
    await state.clear()


class StopById(StatesGroup):
    waiting_for_id = State()


@admin_router.callback_query(F.data == "stop_by_id")
async def stop_by_id_prompt(callback: CallbackQuery, state: FSMContext, lang="ru"):
    await state.clear()
    await state.set_state(StopById.waiting_for_id)
    await callback.answer()
    await callback.message.answer(t(lang, "stop_prompt"), reply_markup=back_to_alerts_keyboard(lang))


@admin_router.message(StopById.waiting_for_id)
async def stop_by_id_submit(mes: Message, state: FSMContext, crypt: CoinGekoCryptoService, lang="ru"):
    task_id = (mes.text or "").strip()
    if task_id not in crypt.list_tasks():
        await mes.answer(t(lang, "not_found"), reply_markup=back_to_alerts_keyboard(lang))
        return
    if not crypt.stop_task(task_id):
        await mes.answer(t(lang, "stop_error"), reply_markup=back_to_alerts_keyboard(lang))
        return
    await state.clear()
    await mes.answer(t(lang, "stop_done", id=task_id), reply_markup=back_to_alerts_keyboard(lang))


@admin_router.callback_query(F.data.in_({"language:ru", "language:en"}))
async def language_callback(callback: CallbackQuery, crypt: CoinGekoCryptoService, lang="ru"):
    selected = callback.data.split(":", 1)[1]
    if not crypt.set_language(selected):
        await callback.answer(t(lang, "save_error"), show_alert=True)
        return
    await callback.answer(t(selected, "language_saved"))
    enabled = crypt.get_autostart()
    await edit_view(callback, settings_text(enabled, selected), sk(enabled, selected))
