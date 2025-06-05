import calendar
from datetime import date, datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
import asyncio
import logging
import csv
import os

import db
from config import BOT_TOKEN, ADMIN_ID

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

db.init_db()

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="Markdown")
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

DAYS_PER_PAGE = 7

def get_month_dates():
    today = date.today()
    year, month = today.year, today.month
    last_day = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, last_day + 1)]

def human_date(date_iso: str) -> str:
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    days_ru = [
        "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"
    ]
    d = datetime.fromisoformat(date_iso).date()
    return f"{d.day} {months[d.month-1]} ({days_ru[d.weekday()]})"

def user_link(user_id: int, username: str = None) -> str:
    if username:
        return f'[пользователь](tg://user?id={user_id}) ({username})'
    else:
        return f'[пользователь](tg://user?id={user_id})'

def build_dates_keyboard(selected, page=0):
    dates = get_month_dates()
    builder = InlineKeyboardBuilder()
    start = page * DAYS_PER_PAGE
    page_dates = dates[start:start + DAYS_PER_PAGE]
    for d in page_dates:
        txt = human_date(d.isoformat())
        if d.isoformat() in selected:
            txt = "✅ " + txt
        builder.button(
            text=txt,
            callback_data=f"date_{d.isoformat()}_{int(d.isoformat() in selected)}_{page}"
        )
    builder.adjust(2)
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{page-1}"))
    if start + DAYS_PER_PAGE < len(dates):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(
        InlineKeyboardButton(text="Готово ✅", callback_data="done"),
        InlineKeyboardButton(text="Сбросить выбор", callback_data="reset"),
    )
    return builder.as_markup()

@router.message(Command("help"))
async def help_command(msg: types.Message):
    text = (
        "*Доступные команды:*\n\n"
        "/start — начать или обновить голосование\n"
        "/vote — выбрать или изменить даты\n"
        "/status — посмотреть выбранные вами даты\n"
        "/help — показать это справочное сообщение\n\n"
        "*Для администратора:*\n"
        "/votes — список пользователей и их выбор\n"
        "/results — количество голосов по каждой дате\n"
        "/results_csv — выгрузка результатов в CSV-файл\n"
        "/not_voted — кто ещё не проголосовал"
    )
    await msg.answer(text)

@router.message(Command("start", "vote"))
async def start_vote(msg: types.Message):
    db.add_user(msg.from_user.id, msg.from_user.username or "")
    selected = db.get_user_votes(msg.from_user.id)
    kb = build_dates_keyboard(selected, 0)
    logging.info(f"User {msg.from_user.id} ({msg.from_user.username}) started vote. Current selection: {selected}")
    await msg.answer(
        "Выберите даты, когда вы *МОЖЕТЕ* прийти на пикник.\n"
        "Можно выбрать несколько дат, выбранные отмечаются галочкой.\n"
        "Нажмите 'Готово ✅' когда закончите.\n\n"
        "Чтобы изменить свой выбор позже — просто снова отправьте /vote.",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("date_"))
async def handle_date_select(call: types.CallbackQuery):
    parts = call.data.split("_")
    d, was_selected, page = parts[1], int(parts[2]), int(parts[3])
    user_id = call.from_user.id
    selected = set(db.get_user_votes(user_id))
    if was_selected:
        selected.discard(d)
        action = "remove"
    else:
        selected.add(d)
        action = "add"
    db.set_user_votes(user_id, list(selected))
    kb = build_dates_keyboard(selected, page)
    logging.info(f"User {user_id} ({call.from_user.username}) {action} date {d}. New selection: {selected}")
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("page_"))
async def handle_page(call: types.CallbackQuery):
    page = int(call.data.split("_")[1])
    user_id = call.from_user.id
    selected = db.get_user_votes(user_id)
    kb = build_dates_keyboard(selected, page)
    logging.info(f"User {user_id} ({call.from_user.username}) navigated to page {page}")
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "done")
async def handle_done(call: types.CallbackQuery):
    user_id = call.from_user.id
    username = call.from_user.username or ""
    selected = db.get_user_votes(user_id)
    if selected:
        txt = "Спасибо! Ваши выбранные даты:\n" + \
            "\n".join([human_date(d) for d in sorted(selected)]) + \
            "\n\nЕсли хотите изменить выбор — снова вызовите /vote."
        await call.message.edit_text(txt)
        logging.info(f"User {user_id} ({username}) confirmed: {selected}")
        try:
            admin_text = (
                f"{user_link(user_id, username)} подтвердил свой выбор:\n"
                + "\n".join([human_date(d) for d in sorted(selected)])
            )
            await bot.send_message(ADMIN_ID, admin_text)
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения админу: {e}")
    else:
        await call.message.edit_text("Вы не выбрали ни одной даты. Можете выбрать позже.")
        logging.info(f"User {user_id} ({username}) tried to confirm but has empty selection")
    await call.answer()

@router.callback_query(F.data == "reset")
async def handle_reset(call: types.CallbackQuery):
    user_id = call.from_user.id
    db.set_user_votes(user_id, [])
    kb = build_dates_keyboard([], 0)
    logging.info(f"User {user_id} ({call.from_user.username}) reset their selection")
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer("Выбор сброшен!")

@router.message(Command("status"))
async def status(msg: types.Message):
    selected = db.get_user_votes(msg.from_user.id)
    if selected:
        txt = "\n".join([human_date(d) for d in sorted(selected)])
        await msg.answer(f"Ваш выбор:\n{txt}\n\nЧтобы изменить — используйте /vote.")
    else:
        await msg.answer("Вы ещё не выбрали даты. Используйте /vote.")
    logging.info(f"User {msg.from_user.id} ({msg.from_user.username}) checked their status")

@router.message(Command("votes"))
async def votes(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    data = db.get_all_votes()
    users = {}
    for user_id, username, vote_date in data:
        if user_id not in users:
            users[user_id] = {"username": username, "dates": []}
        if vote_date:
            users[user_id]["dates"].append(vote_date)
    txt = ""
    for user_id, info in users.items():
        uname = user_link(user_id, info['username'])
        if info["dates"]:
            dates = ", ".join([human_date(d) for d in sorted(info["dates"])])
            txt += f"{uname}: {dates}\n"
        else:
            txt += f"{uname}: не проголосовал\n"
    await msg.answer(f"Кто проголосовал и за что:\n{txt}")
    logging.info("Admin requested /votes")

@router.message(Command("results"))
async def results(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    votes = db.get_votes_by_date()
    if not votes:
        await msg.answer("Пока никто не проголосовал.")
        logging.info("Admin requested /results: no votes")
        return
    txt = "\n".join([f"{human_date(d)}: {cnt} чел." for d, cnt in votes])
    await msg.answer("Результаты голосования по датам:\n" + txt)
    logging.info("Admin requested /results")

@router.message(Command("results_csv"))
async def results_csv(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    votes = db.get_votes_by_date()
    all_votes = db.get_all_votes()
    # Соберем данные по пользователям для вывода ФИО, username и id
    users_info = {}
    for user_id, username, vote_date in all_votes:
        # Для каждой даты у пользователя может быть много строк, но имя и username одни, поэтому запомним для user_id
        if user_id not in users_info:
            user_fullname = ""
            # В aiogram username - str, ФИО - msg.from_user.full_name
            # Но в базе только user_id и username, ФИО не сохранялось.
            # Поэтому будем только username, id, а ФИО оставить пустым если нет.
            users_info[user_id] = {"username": username or "", "fullname": ""}
    # дата -> [(user_id, username, fullname)]
    votes_per_date = {}
    for user_id, username, vote_date in all_votes:
        if vote_date:
            votes_per_date.setdefault(vote_date, []).append(
                (user_id, username or "", "")
            )
    filename = "votes_results.csv"
    with open(filename, "w", newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Дата", "Голосов", "Имя", "Username", "ID"])
        for d, cnt in votes:
            users = votes_per_date.get(d, [])
            # На случай если никто не выбрал дату, users может быть пустым
            if not users:
                writer.writerow([human_date(d), "0", "", "", ""])
            else:
                for u in users:
                    user_id, username, fullname = u
                    writer.writerow([
                        human_date(d),
                        str(cnt),
                        fullname,
                        username,
                        str(user_id)
                    ])
    await bot.send_document(chat_id=ADMIN_ID, document=FSInputFile(filename), caption="CSV с результатами голосования по датам")
    logging.info("Admin requested /results_csv (CSV file sent)")
    try:
        os.remove(filename)
    except Exception as e:
        logging.error(f"Ошибка удаления временного файла: {e}")

@router.message(Command("not_voted"))
async def not_voted(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    all_data = db.get_all_votes()
    user_ids = set(row[0] for row in all_data)
    voted = set(db.get_voted_users())
    not_voted = user_ids - voted
    if not not_voted:
        await msg.answer("Все уже проголосовали!")
        logging.info("Admin requested /not_voted: all voted")
        return
    txt = ""
    for user_id in not_voted:
        uname = [row[1] for row in all_data if row[0] == user_id][0]
        txt += f"{user_link(user_id, uname)}\n"
    await msg.answer("Не проголосовали:\n" + txt)
    logging.info("Admin requested /not_voted")

async def main():
    logging.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())