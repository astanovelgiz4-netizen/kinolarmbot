import os
import asyncio
import sqlite3
import logging
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent
)

# --- BOT TOKEN VA ADMIN ID ---
TOKEN = "7748673962:AAE0KUclQJs6xcwlsFnKvcmhvfl5TpwsxYI"
ADMIN_ID = 6884014716

# --- WEB SERVER (24/7 uchun) ---
app = Flask("")

@app.route('/')
def home():
    return "Bot ishlayapti!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run).start()

# --- BOT INIT ---
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# --- DATABASE INIT ---
def init_db():
    conn = sqlite3.connect("baza.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY, chat_id TEXT, link TEXT)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            title TEXT,
            file_id TEXT,
            genre TEXT,
            lang TEXT,
            country TEXT,
            year TEXT,
            views INTEGER DEFAULT 0
        )
    """)
    cur.execute("CREATE TABLE IF NOT EXISTS saved (user_id INTEGER, movie_id INTEGER)")
    conn.commit()
    conn.close()

# --- ADMIN STATES ---
class AdminState(StatesGroup):
    add_channel = State()
    broadcast = State()
    add_movie_video = State()
    add_movie_details = State()

# --- KEYBOARDS ---
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Film qidirish"), KeyboardButton(text="⭐ Saqlanganlar")],
            [KeyboardButton(text="🔝 Top kinolar"), KeyboardButton(text="🎲 Tasodifiy")],
            [KeyboardButton(text="🎞 Barcha filmlar"), KeyboardButton(text="📩 Murojaat")]
        ],
        resize_keyboard=True
    )

def filter_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Nom orqali (Inline)", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="🎭 Janr", callback_data="f_genre"), InlineKeyboardButton(text="🗣 Til", callback_data="f_lang")],
            [InlineKeyboardButton(text="🌍 Davlat", callback_data="f_country"), InlineKeyboardButton(text="📅 Yil", callback_data="f_year")],
            [InlineKeyboardButton(text="🛍 Buyurtma berish", callback_data="order")]
        ]
    )

# --- CHECK SUBSCRIPTION ---
async def is_subscribed(user_id):
    conn = sqlite3.connect("baza.db")
    cur = conn.cursor()
    cur.execute("SELECT chat_id, link FROM channels")
    chans = cur.fetchall()
    conn.close()
    unsub = []
    for cid, link in chans:
        try:
            member = await bot.get_chat_member(cid, user_id)
            if member.status in ['left', 'kicked']:
                unsub.append(link)
        except:
            continue
    return unsub

# --- HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect("baza.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

    unsub = await is_subscribed(message.from_user.id)
    if unsub:
        btn = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="A'zo bo'lish", url=l)] for l in unsub]
        )
        btn.inline_keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check")])
        return await message.answer("Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=btn)

    await message.answer("Xush kelibsiz! Kino kodini yuboring:", reply_markup=main_menu())

# Kino kodini qabul qilish
@dp.message(lambda m: m.text and m.text.isdigit())
async def get_kino(message: types.Message):
    conn = sqlite3.connect("baza.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM movies WHERE code = ?", (message.text,))
    m = cur.fetchone()
    if m:
        cur.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (message.text,))
        conn.commit()
        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Saqlash", callback_data=f"save_{m[0]}")]])
        cap = f"🎬 {m[2]}\n\n🎭 Janr: {m[4]}\n🗣 Til: {m[5]}\n📅 Yil: {m[7]}\n👁 Ko'rildi: {m[8]+1}"
        await message.answer_video(m[3], caption=cap, reply_markup=btn)
    else:
        await message.answer("Kino topilmadi.")
    conn.close()

@dp.message(lambda m: m.text == "🔍 Film qidirish")
async def search_f(message: types.Message):
    await message.answer("Qidiruv usulini tanlang:", reply_markup=filter_menu())

# --- INLINE SEARCH ---
@dp.inline_query()
async def inline_search(query: types.InlineQuery):
    conn = sqlite3.connect("baza.db")
    cur = conn.cursor()
    cur.execute("SELECT code, title, genre FROM movies WHERE title LIKE ?", (f"%{query.query}%",))
    res = cur.fetchall()
    conn.close()
    articles = [
        InlineQueryResultArticle(
            id=str(r[0]),
            title=r[1],
            description=f"Janr: {r[2]}",
            input_message_content=InputTextMessageContent(message_text=r[0])
        )
        for r in res[:15]
    ]
    await query.answer(articles, cache_time=1)

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_p(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    btn = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="add_k"), InlineKeyboardButton(text="📢 Kanal", callback_data="add_c")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stat"), InlineKeyboardButton(text="✉️ Rassilka", callback_data="send")]
        ]
    )
    await message.answer("Admin Panel:", reply_markup=btn)

@dp.callback_query(lambda c: c.data == "add_k")
async def add_k(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Kino videosini yuboring:")
    await state.set_state(AdminState.add_movie_video)

@dp.message(AdminState.add_movie_video, content_types=types.ContentType.VIDEO)
async def add_v(message: types.Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await message.answer("Ma'lumotlarni yuboring:\nkod | nomi | janr | til | davlat | yil", parse_mode="Markdown")
    await state.set_state(AdminState.add_movie_details)

@dp.message(AdminState.add_movie_details)
async def add_d(message: types.Message, state: FSMContext):
    d = message.text.split("|")
    if len(d) != 6:
        return await message.answer("Iltimos, to'liq ma'lumot yuboring: kod | nomi | janr | til | davlat | yil")
    data = await state.get_data()
    conn = sqlite3.connect("baza.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO movies (code, title, file_id, genre, lang, country, year) VALUES (?,?,?,?,?,?,?)",
        (d[0].strip(), d[1].strip(), data['file_id'], d[2].strip(), d[3].strip(), d[4].strip(), d[5].strip())
    )
    conn.commit()
    conn.close()
    await message.answer("Kino qo'shildi!")
    await state.clear()

# --- MAIN ---
async def main():
    init_db()
    keep_alive()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
