#API_TOKEN = "7908411125:AAFxJdhRYxke3mLVRa4Gxxy1Ow2dNk4Sf5w"

import asyncio
from db import connection

import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

API_TOKEN = "7908411125:AAFxJdhRYxke3mLVRa4Gxxy1Ow2dNk4Sf5w"



# ─── 1) Определяем FSM-состояния ─────────────────────────────
class Settings(StatesGroup):
    tax = State()  # ждём ввода процента налогов
    meas_menu = State()  # показ подменю «Стоимость замеров»
    meas_fix = State()  # ввод фиксированной стоимости
    meas_km = State()  # ввод стоимости за км
    master_menu = State()  # выбор типа камня
    master_type = State()  # показ меню зарплат выбранного типа
    master_input = State()  # ввод суммы для конкретного пункта
    salary_role = State()  # вошли в зарплату (уже известна роль)
    salary_stone = State()  # выбрали акрил/кварц
    salary_item = State()  # выбрали пункт меню (столешница/…)
    menu2 = State()  # второй экран меню
    stone2 = State()  # ввод «Тип камня» на меню 2
    price_meter = State()  # ввод «Цена за метр» на меню 2
    menu2_item = State()  # для ввода Столешница/Стеновая/…/Бортики
    menu2_takelage = State()  # *** новое состояние для выбора «такелаж» ***
    # ─── добавляем подменю 3 ────────────────────────────────
    menu3 = State()  # сам экран «меню 3»
    menu3_km = State()  # ввод «Сколько КМ?»
    menu3_mop = State()  # ввод «проценты МОПу»
    menu3_margin = State()  # ввод «маржа»

# ─── 2) Инициализация базы ────────────────────────────────────
async def init_db():
    async with connection() as db:
        # 1) Создаём основную таблицу (unit + tax_percent)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                chat_id                   INTEGER PRIMARY KEY,
                unit                      TEXT    DEFAULT 'не выбрано',
                tax_percent               TEXT    DEFAULT 'не указано',
                measurement_fix           TEXT    DEFAULT 'не указано',
                measurement_km            TEXT    DEFAULT 'не указано',
                master_acryl_countertop   TEXT    DEFAULT 'не указано',
                master_acryl_wall         TEXT    DEFAULT 'не указано',
                master_acryl_boil         TEXT    DEFAULT 'не указано',
                master_acryl_sink         TEXT    DEFAULT 'не указано',
                master_acryl_glue         TEXT    DEFAULT 'не указано',
                master_acryl_edges        TEXT    DEFAULT 'не указано',
                master_quartz_countertop  TEXT    DEFAULT 'не указано',
                master_quartz_wall        TEXT    DEFAULT 'не указано',
                master_quartz_boil        TEXT    DEFAULT 'не указано',
                master_quartz_sink        TEXT    DEFAULT 'не указано',
                master_quartz_glue        TEXT    DEFAULT 'не указано',
                master_quartz_edges       TEXT    DEFAULT 'не указано'
            )
        """)
        # 2) Узнаём, какие колонки уже есть
        cursor = await db.execute("PRAGMA table_info(user_settings)")
        cols = [row[1] for row in await cursor.fetchall()]

        # 3) Обязательно добавляем measurement-колонки
        for col in ("measurement_fix", "measurement_km"):
            if col not in cols:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'")

        # 4) И добавляем все master_* колонки
        master_cols = [
            "master_acryl_countertop","master_acryl_wall",
            "master_acryl_boil","master_acryl_sink",
            "master_acryl_glue","master_acryl_edges",
            "master_quartz_countertop","master_quartz_wall",
            "master_quartz_boil","master_quartz_sink",
            "master_quartz_glue","master_quartz_edges",
        ]
        installer_cols = [
            "installer_acryl_countertop", "installer_acryl_wall",
            "installer_acryl_delivery", "installer_acryl_takelage",
            "installer_quartz_countertop", "installer_quartz_wall",
            "installer_quartz_delivery", "installer_quartz_takelage",
        ]
        for col in master_cols:
            if col not in cols:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'")
        for col in installer_cols:
            if col not in cols:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'")
        # ─── добавляем колонки для меню 2 ────────────────────────
        if "general_stone_type" not in cols:
            await db.execute("ALTER TABLE user_settings ADD COLUMN general_stone_type TEXT DEFAULT 'не указано'")
        if "price_per_meter" not in cols:
            await db.execute("ALTER TABLE user_settings ADD COLUMN price_per_meter TEXT DEFAULT 'не указано'")

        # ─── меню 2: шесть полей для ручного ввода ─────────────────
        for col in ("menu2_countertop", "menu2_wall", "menu2_boil", "menu2_sink", "menu2_glue", "menu2_edges"):
            if col not in cols:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'")

        # *** ДОБАВЛЯЕМ новую колонку для Такелаж ***
            if "menu2_takelage" not in cols:
                await db.execute("ALTER TABLE user_settings ADD COLUMN menu2_takelage TEXT DEFAULT 'не указано'")

        # ─── добавляем колонки для меню 3 ────────────────────────
        for col in ("menu3_km", "menu3_mop", "menu3_margin"):
            if col not in cols:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'")

        await db.commit()

# ─── конец init_db() ──────────────────────────────────────────


# ─── 3) Работа с БД ──────────────────────────────────────────
async def get_unit(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT unit FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не выбрано"


async def set_unit(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, unit)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET unit = excluded.unit
        """, (chat_id, value))
        await db.commit()


async def get_tax(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT tax_percent FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"


async def set_tax(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, tax_percent)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET tax_percent = excluded.tax_percent
        """, (chat_id, value))
        await db.commit()

# ─── вставьте ниже утилиты для measurement ──────────────────
async def get_measurement_fix(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT measurement_fix FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_measurement_fix(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, measurement_fix)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET measurement_fix = excluded.measurement_fix
        """, (chat_id, value))
        await db.commit()

async def get_measurement_km(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT measurement_km FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def get_master_salary(chat_id: int, key: str) -> str:
    async with connection() as db:
        cur = await db.execute(f"SELECT {key} FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_master_salary(chat_id: int, key: str, value: str):
    async with connection() as db:
        await db.execute(f"""
            INSERT INTO user_settings(chat_id, {key})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {key}=excluded.{key}
        """, (chat_id, value))
        await db.commit()

# ─── вставьте сразу после set_master_salary ─────────────────
async def get_salary(chat_id: int, column: str) -> str:
    async with connection() as db:
        cur = await db.execute(f"SELECT {column} FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_salary(chat_id: int, column: str, value: str):
    async with connection() as db:
        await db.execute(f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column}=excluded.{column}
        """, (chat_id, value))
        await db.commit()
# ─── дальше идут измерения и основной код ───────────────────

# ─── после set_salary добавьте:
async def get_general_stone_type(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute(
            "SELECT general_stone_type FROM user_settings WHERE chat_id = ?", (chat_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_general_stone_type(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, general_stone_type)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET general_stone_type = excluded.general_stone_type
        """, (chat_id, value))
        await db.commit()

async def get_price_per_meter(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute(
            "SELECT price_per_meter FROM user_settings WHERE chat_id = ?", (chat_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

# ─── после set_price_per_meter ───────────────────────────────
async def get_menu2_countertop(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu2_countertop FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_countertop(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu2_countertop)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu2_countertop = excluded.menu2_countertop
        """, (chat_id, value))
        await db.commit()

async def get_menu2_wall(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu2_wall FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_wall(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu2_wall)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu2_wall = excluded.menu2_wall
        """, (chat_id, value))
        await db.commit()

async def get_menu2_boil(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu2_boil FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_boil(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu2_boil)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu2_boil = excluded.menu2_boil
        """, (chat_id, value))
        await db.commit()

async def get_menu2_sink(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu2_sink FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_sink(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu2_sink)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu2_sink = excluded.menu2_sink
        """, (chat_id, value))
        await db.commit()

async def get_menu2_glue(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu2_glue FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_glue(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu2_glue)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu2_glue = excluded.menu2_glue
        """, (chat_id, value))
        await db.commit()

async def get_menu2_edges(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu2_edges FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_edges(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu2_edges)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu2_edges = excluded.menu2_edges
        """, (chat_id, value))
        await db.commit()

# … после get_menu2_edges и set_menu2_edges …
async def get_menu2_takelage(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu2_takelage FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_takelage(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu2_takelage)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu2_takelage = excluded.menu2_takelage
        """, (chat_id, value))
        await db.commit()

async def menu2_takelage_menu(call: CallbackQuery, state: FSMContext):
    # 1) Переводим FSM в состояние Settings.menu2_takelage
    await state.set_state(Settings.menu2_takelage)
    data = await state.get_data()
    await state.update_data(menu2_message_id=data["menu2_message_id"])

    # 2) Показываем юзеру две кнопки «Да» / «Нет»
    await call.message.edit_text(
        "Такелаж: выберите «Да» или «Нет»:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да",  callback_data="takel_yes")],
            [InlineKeyboardButton(text="Нет", callback_data="takel_no")],
        ])
    )
    await call.answer()


# ─── геттеры/сеттеры для меню 3 ─────────────────────────────
async def get_menu3_km(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu3_km FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu3_km(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu3_km)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu3_km = excluded.menu3_km
        """, (chat_id, value))
        await db.commit()

async def get_menu3_mop(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu3_mop FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu3_mop(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu3_mop)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu3_mop = excluded.menu3_mop
        """, (chat_id, value))
        await db.commit()

async def get_menu3_margin(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT menu3_margin FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu3_margin(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu3_margin)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu3_margin = excluded.menu3_margin
        """, (chat_id, value))
        await db.commit()

# ─── далее продолжается остальной код ────────────────────────

async def set_price_per_meter(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, price_per_meter)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET price_per_meter = excluded.price_per_meter
        """, (chat_id, value))
        await db.commit()
# ─── далее идёт ваша логика меню/хендлеров ───────────────────


async def set_measurement_km(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, measurement_km)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET measurement_km = excluded.measurement_km
        """, (chat_id, value))
        await db.commit()
# ─── после этой строки идут функции main_menu и далее ────────

# ─── 4) Построение главного меню ─────────────────────────────
def main_menu(unit_value: str, tax_value: str, fix_value: str, km_value: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Единица измерения | {unit_value}", callback_data="set_unit")],
        [InlineKeyboardButton(text="ЗП Мастера", callback_data="salary_master")],
        [InlineKeyboardButton(text="ЗП Монтажника", callback_data="salary_installer")],
        [InlineKeyboardButton(text=f"Система налогов | {tax_value}%", callback_data="set_tax_system")],
        [InlineKeyboardButton(
            text=f"Стоимость замеров | Фикс {fix_value} | КМ {km_value}",
            callback_data="set_measurement_cost"
        )],
        [InlineKeyboardButton(text="Далее", callback_data="to_menu2")],
    ])

# ─── вставьте здесь подменю measurement ─────────────────────
def meas_submenu(fix: str, km: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Фикс | {fix}",        callback_data="meas_fix"),
            InlineKeyboardButton(text=f"Стоимость КМ | {km}", callback_data="meas_km"),
        ],
        [InlineKeyboardButton(text="← Назад", callback_data="meas_back")],
    ])

# ─── вставьте после meas_submenu ───────────────────────────
def stone_menu_kb(role: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акрил",  callback_data=f"salary_{role}_acryl")],
        [InlineKeyboardButton(text="Кварц",  callback_data=f"salary_{role}_quartz")],
        [InlineKeyboardButton(text="← Назад", callback_data=f"salary_{role}_stone_back")],
    ])

def salary_item_kb(role: str, stone: str, unit: str, values: dict[str,str]) -> InlineKeyboardMarkup:
    # для мастера: countertop, wall, boil, sink, glue, edges
    # для монтажника: countertop, wall, delivery, takelage
    kb = []
    if role == "master":
        kb += [[
            InlineKeyboardButton(text=f"Столешница | {values['countertop']} | {unit}", callback_data=f"salary_{role}_{stone}_countertop")
        ],[
            InlineKeyboardButton(text=f"Стеновая | {values['wall']} | {unit}", callback_data=f"salary_{role}_{stone}_wall")
        ],[
            InlineKeyboardButton(text=f"Вырез варка | {values['boil']}",      callback_data=f"salary_{role}_{stone}_boil"),
            InlineKeyboardButton(text=f"Вырез мойка | {values['sink']}",      callback_data=f"salary_{role}_{stone}_sink")
        ],[
            InlineKeyboardButton(text=f"Подклейка | {values['glue']}",         callback_data=f"salary_{role}_{stone}_glue"),
            InlineKeyboardButton(text=f"Бортики | {values['edges']} | {unit}", callback_data=f"salary_{role}_{stone}_edges")
        ]]
    else:  # installer
        kb += [[
            InlineKeyboardButton(text=f"Столешница | {values['countertop']} | {unit}", callback_data=f"salary_{role}_{stone}_countertop")
        ],[
            InlineKeyboardButton(text=f"Стеновая | {values['wall']} | {unit}",       callback_data=f"salary_{role}_{stone}_wall")
        ],[
            InlineKeyboardButton(text=f"Доставка | {values['delivery']}",            callback_data=f"salary_{role}_{stone}_delivery"),
            InlineKeyboardButton(text=f"Такелаж | {values['takelage']} | {unit}",     callback_data=f"salary_{role}_{stone}_takelage")
        ]]
    kb.append([InlineKeyboardButton(text="← Назад", callback_data=f"salary_{role}_stone_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ─── Новый блок: меню 2 ──────────────────────────────────────
def menu2_kb(stone: str, price: str,
             cntp: str, wal: str, bo: str, si: str, gl: str, ed: str,
             tak: str, unit: str) -> InlineKeyboardMarkup:
    """
    Теперь menu2_kb получает 10 аргументов:
    1) stone  – выбранный тип камня
    2) price  – цена за метр
    3) cntp   – Столешница
    4) wal    – Стеновая
    5) bo     – Вырез варка
    6) si     – Вырез мойка
    7) gl     – Подклейка
    8) ed     – Бортики
    9) tak    – Такелаж ("да" или "нет" или "не указано")
    10) unit  – единица измерения ("м2"/"м/п")
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Тип камня | {stone}",        callback_data="set_first_stone")],
        [InlineKeyboardButton(text=f"Цена за метр | {price}",     callback_data="set_price_meter")],
        [InlineKeyboardButton(text=f"Столешница | {cntp} | {unit}", callback_data="menu2_countertop")],
        [InlineKeyboardButton(text=f"Стеновая | {wal} | {unit}",   callback_data="menu2_wall")],
        [
          InlineKeyboardButton(text=f"Вырез варка | {bo} шт",      callback_data="menu2_boil"),
          InlineKeyboardButton(text=f"Вырез мойка | {si} шт",      callback_data="menu2_sink"),
        ],
        [
          InlineKeyboardButton(text=f"Подклейка | {gl} шт",         callback_data="menu2_glue"),
          InlineKeyboardButton(text=f"Бортики | {ed} | {unit}",    callback_data="menu2_edges"),
        ],
        # *** новая строка с кнопкой «Такелаж» ***
        [InlineKeyboardButton(text=f"Такелаж | {tak}",              callback_data="menu2_takelage")],

        # далее оставшиеся кнопки:
        [InlineKeyboardButton(text="Далее", callback_data="to_menu3")],
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_main")],
    ])


def first_stone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акрил",  callback_data="stone2_acryl")],
        [InlineKeyboardButton(text="Кварц",  callback_data="stone2_quartz")],
    ])


def menu3_kb(km: str, mop: str, margin: str) -> InlineKeyboardMarkup:
    """
    km, mop, margin — текущие сохранённые строки («не указано» или уже введённое значение).
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Сколько КМ? {km} км",      callback_data="menu3_km")],
        [InlineKeyboardButton(text=f"проценты МОПу {mop} %",   callback_data="menu3_mop")],
        [InlineKeyboardButton(text=f"маржа {margin} %",         callback_data="menu3_margin")],
        [
            InlineKeyboardButton(text="← Назад",                callback_data="back_to_menu2"),
            InlineKeyboardButton(text="Рассчитать",            callback_data="calculate")
        ],
    ])

# ─── 5) Хендлеры ───────────────────────────────────────────────
async def start_handler(message: Message, state: FSMContext):
    # Сбросим любое текущее состояние
    await state.clear()

    unit = await get_unit(message.chat.id)
    tax  = await get_tax(message.chat.id)
    fix = await get_measurement_fix(message.chat.id)
    km = await get_measurement_km(message.chat.id)
    await message.answer("Привет! Настройте параметры:", reply_markup=main_menu(unit, tax, fix, km))

# ─── Хендлеры меню 3 ─────────────────────────────────────────

async def to_menu3(call: CallbackQuery, state: FSMContext):
    # Переходим в состояние меню3
    await state.set_state(Settings.menu3)
    await state.update_data(menu3_message_id=call.message.message_id)

    km_current     = await get_menu3_km(call.message.chat.id)
    mop_current    = await get_menu3_mop(call.message.chat.id)
    margin_current = await get_menu3_margin(call.message.chat.id)

    await call.message.edit_text(
        "Основное меню 3:",
        reply_markup=menu3_kb(km_current, mop_current, margin_current)
    )
    await call.answer()


async def menu3_km_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu3_km)
    data = await state.get_data()
    await state.update_data(menu3_message_id=data["menu3_message_id"])
    await call.message.edit_text("Введите количество КМ (целое число):")
    await call.answer()

async def menu3_km_input(message: Message, state: FSMContext):
    data       = await state.get_data()
    menu3_id   = data["menu3_message_id"]
    text       = message.text.strip()
    if not text.isdigit():
        return await message.reply("Неверный формат. Введите целое число, например: 10")
    await set_menu3_km(message.chat.id, text)
    await message.delete()

    await state.set_state(Settings.menu3)
    km_current     = await get_menu3_km(message.chat.id)
    mop_current    = await get_menu3_mop(message.chat.id)
    margin_current = await get_menu3_margin(message.chat.id)
    await message.bot.edit_message_text(
        text="Основное меню 3:",
        chat_id=message.chat.id,
        message_id=menu3_id,
        reply_markup=menu3_kb(km_current, mop_current, margin_current)
    )


async def menu3_mop_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu3_mop)
    data = await state.get_data()
    await state.update_data(menu3_message_id=data["menu3_message_id"])
    await call.message.edit_text("Введите проценты МОПу (целое число от 0 до 100):")
    await call.answer()

async def menu3_mop_input(message: Message, state: FSMContext):
    data       = await state.get_data()
    menu3_id   = data["menu3_message_id"]
    text       = message.text.strip()
    if not text.isdigit() or not (0 <= int(text) <= 100):
        return await message.reply("Неверный формат. Введите целое число от 0 до 100.")
    await set_menu3_mop(message.chat.id, text)
    await message.delete()

    await state.set_state(Settings.menu3)
    km_current     = await get_menu3_km(message.chat.id)
    mop_current    = await get_menu3_mop(message.chat.id)
    margin_current = await get_menu3_margin(message.chat.id)
    await message.bot.edit_message_text(
        text="Основное меню 3:",
        chat_id=message.chat.id,
        message_id=menu3_id,
        reply_markup=menu3_kb(km_current, mop_current, margin_current)
    )


async def menu3_margin_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu3_margin)
    data = await state.get_data()
    await state.update_data(menu3_message_id=data["menu3_message_id"])
    await call.message.edit_text("Введите маржу в % (целое число от 0 до 100):")
    await call.answer()

async def menu3_margin_input(message: Message, state: FSMContext):
    data       = await state.get_data()
    menu3_id   = data["menu3_message_id"]
    text       = message.text.strip()
    if not text.isdigit() or not (0 <= int(text) <= 100):
        return await message.reply("Неверный формат. Введите целое число от 0 до 100.")
    await set_menu3_margin(message.chat.id, text)
    await message.delete()

    await state.set_state(Settings.menu3)
    km_current     = await get_menu3_km(message.chat.id)
    mop_current    = await get_menu3_mop(message.chat.id)
    margin_current = await get_menu3_margin(message.chat.id)
    await message.bot.edit_message_text(
        text="Основное меню 3:",
        chat_id=message.chat.id,
        message_id=menu3_id,
        reply_markup=menu3_kb(km_current, mop_current, margin_current)
    )


async def back_to_menu2(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu2)
    chat_id = call.message.chat.id
    data    = await state.get_data()
    menu2_id = data["menu2_message_id"]

    current_stone  = await get_general_stone_type(chat_id)
    current_price  = await get_price_per_meter(chat_id)
    unit           = await get_unit(chat_id)
    cntp = await get_menu2_countertop(chat_id)
    wal  = await get_menu2_wall(chat_id)
    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_edges(chat_id)
    tak  = await get_menu2_takelage(chat_id)  # <<< читаем

    await call.message.edit_text(
        "Основное меню 2:",
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            tak,                # <<< сюда
            unit
        )
    )
    await call.answer()


async def set_unit_menu(call: CallbackQuery, state: FSMContext):
    # Сохраним ID этого сообщения, чтобы потом редактировать его обратно
    await state.update_data(menu_message_id=call.message.message_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="м2",   callback_data="unit_m2"),
            InlineKeyboardButton(text="м/п", callback_data="unit_mp"),
        ]
    ])
    await call.message.edit_text("Выберите единицу измерения:", reply_markup=kb)
    await call.answer()


async def unit_choice(call: CallbackQuery, state: FSMContext):
    choice = "м2" if call.data == "unit_m2" else "м/п"
    await set_unit(call.message.chat.id, choice)

    data = await state.get_data()
    menu_id = data.get("menu_message_id")

    # Снова получаем обе настройки и редактируем то же сообщение
    unit = await get_unit(call.message.chat.id)
    tax  = await get_tax(call.message.chat.id)
    fix = await get_measurement_fix(call.message.chat.id)
    km = await get_measurement_km(call.message.chat.id)
    await call.message.bot.edit_message_text(
        text="Параметры:",
        chat_id=call.message.chat.id,
        message_id=menu_id,
        reply_markup=main_menu(unit, tax, fix, km)
    )
    await call.answer()


async def set_tax_menu(call: CallbackQuery, state: FSMContext):
    # Переходим в состояние ввода налога
    await state.set_state(Settings.tax)
    # Сохраняем ID этого сообщения
    await state.update_data(menu_message_id=call.message.message_id)
    # Редактируем его под запрос
    await call.message.edit_text("Введи, какой процент налогов ты платишь:")
    await call.answer()


async def tax_input(message: Message, state: FSMContext):
    data = await state.get_data()
    menu_id = data.get("menu_message_id")

    text = message.text.strip().rstrip('%')
    if not text.isdigit():
        return await message.reply("Неверный формат. Введите число (например, 15).")

    # 1) Сохраняем процент в БД
    await set_tax(message.chat.id, text)

    # 2) Удаляем сообщение пользователя с цифрой
    await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

    # 3) Завершаем FSM-состояние
    await state.clear()

    # 4) Редактируем то же сообщение-меню
    unit = await get_unit(message.chat.id)
    tax  = await get_tax(message.chat.id)
    fix = await get_measurement_fix(message.chat.id)
    km = await get_measurement_km(message.chat.id)
    await message.bot.edit_message_text(
        text="Параметры:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=main_menu(unit, tax, fix, km)
    )

# ─── вставьте сюда хендлеры для measurement ────────────────
async def set_measurement_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.meas_menu)
    await state.update_data(menu_message_id=call.message.message_id)
    fix = await get_measurement_fix(call.message.chat.id)
    km  = await get_measurement_km(call.message.chat.id)
    await call.message.edit_text("Введите стоимость выезда:", reply_markup=meas_submenu(fix, km))
    await call.answer()

async def meas_fix_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.meas_fix)
    data = await state.get_data()
    await state.update_data(menu_message_id=data["menu_message_id"])
    await call.message.edit_text("Введите фиксированную стоимость выезда для замеров (₽):")
    await call.answer()

async def meas_km_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.meas_km)
    data = await state.get_data()
    await state.update_data(menu_message_id=data["menu_message_id"])
    await call.message.edit_text("Введите стоимость одного километра (₽):")
    await call.answer()

async def meas_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    unit = await get_unit(call.message.chat.id)
    tax  = await get_tax(call.message.chat.id)
    fix  = await get_measurement_fix(call.message.chat.id)
    km   = await get_measurement_km(call.message.chat.id)
    await call.message.edit_text("Параметры:", reply_markup=main_menu(unit, tax, fix, km))
    await call.answer()

async def meas_fix_input(message: Message, state: FSMContext):
    data    = await state.get_data()
    menu_id = data["menu_message_id"]
    text    = message.text.strip().rstrip('₽')
    if not text.isdigit():
        return await message.reply("Введите число, например: 3000")
    await set_measurement_fix(message.chat.id, text)
    await message.delete()
    await state.set_state(Settings.meas_menu)
    fix = await get_measurement_fix(message.chat.id)
    km  = await get_measurement_km(message.chat.id)
    await message.bot.edit_message_text(
        text="Введите стоимость выезда:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=meas_submenu(fix, km)
    )

async def meas_km_input(message: Message, state: FSMContext):
    data    = await state.get_data()
    menu_id = data["menu_message_id"]
    text    = message.text.strip().rstrip('₽')
    if not text.isdigit():
        return await message.reply("Введите число, например: 20")
    await set_measurement_km(message.chat.id, text)
    await message.delete()
    await state.set_state(Settings.meas_menu)
    fix = await get_measurement_fix(message.chat.id)
    km  = await get_measurement_km(message.chat.id)
    await message.bot.edit_message_text(
        text="Введите стоимость выезда:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=meas_submenu(fix, km)
    )

async def salary_role_menu(call: CallbackQuery, state: FSMContext):
    # call.data == "salary_master" или "salary_installer"
    role = call.data.split("_")[1]      # -> "master" или "installer"
    await state.set_state(Settings.salary_role)
    await state.update_data(menu_message_id=call.message.message_id, role=role)
    await call.message.edit_text(
        "Выберите тип камня:",
        reply_markup=stone_menu_kb(role)
    )
    await call.answer()


async def salary_stone_choice(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role, stone = data["role"], call.data.split("_")[2]
    await state.set_state(Settings.salary_stone)
    await state.update_data(stone=stone)
    unit = await get_unit(call.message.chat.id)
    # забираем текущие значения
    keys = ["countertop","wall"]
    if role=="master":
        keys += ["boil","sink","glue","edges"]
    else:
        keys += ["delivery","takelage"]
    values = {k: await get_salary(call.message.chat.id, f"master_{stone}_{k}" if role=="master" else f"installer_{stone}_{k}")
              for k in keys}
    await call.message.edit_text(
        f"Установки для { 'акрилового' if stone=='acryl' else 'кварцевого' } камня:",
        reply_markup=salary_item_kb(role, stone, unit, values)
    )
    await call.answer()

async def salary_stone_back(call: CallbackQuery, state: FSMContext):
    # Возвращаемся в главное меню
    await state.clear()
    unit = await get_unit(call.message.chat.id)
    tax  = await get_tax(call.message.chat.id)
    fix  = await get_measurement_fix(call.message.chat.id)
    km   = await get_measurement_km(call.message.chat.id)
    await call.message.edit_text(
        "Параметры:",
        reply_markup=main_menu(unit, tax, fix, km)
    )
    await call.answer()

async def salary_item_menu(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role, stone, menu_id = data["role"], data["stone"], data["menu_message_id"]
    item = call.data.split("_")[-1]  # типа countertop или delivery
    await state.set_state(Settings.salary_item)
    await state.update_data(item=item)
    # текстовый запрос
    label = {
      "countertop":"Столешница","wall":"Стеновая",
      "boil":"Вырез варка","sink":"Вырез мойка",
      "glue":"Подклейка","edges":"Бортики",
      "delivery":"Доставка","takelage":"Такелаж",
    }[item]
    await call.message.edit_text(f"Введите сумму для {label} ({'м2' if item in ['countertop','wall','edges','takelage'] else 'шт.'}):")
    await call.answer()

async def salary_item_input(message: Message, state: FSMContext):
    data   = await state.get_data()
    menu_id= data["menu_message_id"]
    role, stone, item = data["role"], data["stone"], data["item"]
    text   = message.text.strip()
    if not text.isdigit():
        return await message.reply("Введите число, например: 1500")
    await set_salary(
        message.chat.id,
        f"{role}_{stone}_{item}",
        text
    )
    await message.delete()
    # возвращаемся в меню items
    await state.set_state(Settings.salary_stone)
    unit = await get_unit(message.chat.id)
    # заново собрать values как в B)
    keys = ["countertop","wall"] + (["boil","sink","glue","edges"] if role=="master" else ["delivery","takelage"])
    values = {k: await get_salary(message.chat.id, f"{role}_{stone}_{k}") for k in keys}
    await message.bot.edit_message_text(
        text=f"Установки для { 'акрилового' if stone=='acryl' else 'кварцевого' } камня:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=salary_item_kb(role, stone, unit, values)
    )

# ─── 6) Хендлеры для меню 2 ──────────────────────────────────

async def to_menu2(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu2)
    await state.update_data(menu2_message_id=call.message.message_id)

    chat_id = call.message.chat.id
    current_stone  = await get_general_stone_type(chat_id)
    current_price  = await get_price_per_meter(chat_id)
    unit           = await get_unit(chat_id)
    cntp           = await get_menu2_countertop(chat_id)
    wal            = await get_menu2_wall(chat_id)
    bo             = await get_menu2_boil(chat_id)
    si             = await get_menu2_sink(chat_id)
    gl             = await get_menu2_glue(chat_id)
    ed             = await get_menu2_edges(chat_id)
    tak            = await get_menu2_takelage(chat_id)   # <<< читаем новое поле

    await call.message.edit_text(
        "Основное меню 2:",
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            tak,         # <<< передаем его
            unit
        )
    )
    await call.answer()


async def first_stone_choice(call: CallbackQuery, state: FSMContext):
    # Переходим в подменю выбора «Тип камня»
    await state.set_state(Settings.stone2)
    # Сохраняем ID сообщения, чтобы потом вернуться
    data = await state.get_data()
    await state.update_data(menu2_message_id=data["menu2_message_id"])
    await call.message.edit_text(
        "Выберите тип камня:",
        reply_markup=first_stone_kb()
    )
    await call.answer()

async def stone2_selected(call: CallbackQuery, state: FSMContext):
    chat_id = call.message.chat.id
    selected = "акрил" if call.data == "stone2_acryl" else "кварц"
    await set_general_stone_type(chat_id, selected)

    data    = await state.get_data()
    menu2_id = data["menu2_message_id"]

    current_price = await get_price_per_meter(chat_id)
    unit          = await get_unit(chat_id)
    cntp = await get_menu2_countertop(chat_id)
    wal  = await get_menu2_wall(chat_id)
    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_edges(chat_id)
    tak  = await get_menu2_takelage(chat_id)  # <<< вот он

    await call.message.edit_text(
        "Основное меню 2:",
        reply_markup=menu2_kb(
            selected,           # тип камня
            current_price,
            cntp, wal, bo, si, gl, ed,
            tak,                # <<< и передаём
            unit
        )
    )
    await state.set_state(Settings.menu2)
    await call.answer(f"Выбрано: {selected}")



async def price_meter_menu(call: CallbackQuery, state: FSMContext):
    # Переключаемся в состояние ввода цены за метр
    await state.set_state(Settings.price_meter)
    data = await state.get_data()
    await state.update_data(menu2_message_id=data["menu2_message_id"])
    await call.message.edit_text("Введите цену за метр (только цифры):")
    await call.answer()

async def price_meter_input(message: Message, state: FSMContext):
    data     = await state.get_data()
    menu2_id = data["menu2_message_id"]
    text     = message.text.strip()
    if not text.isdigit():
        return await message.reply("Неверно. Введите число, например: 5000")

    chat_id = message.chat.id
    await set_price_per_meter(chat_id, text)
    await message.delete()

    await state.set_state(Settings.menu2)

    current_stone  = await get_general_stone_type(chat_id)
    current_price  = text
    unit           = await get_unit(chat_id)
    cntp = await get_menu2_countertop(chat_id)
    wal  = await get_menu2_wall(chat_id)
    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_edges(chat_id)
    tak  = await get_menu2_takelage(chat_id)  # <<< читаем такелаж

    await message.bot.edit_message_text(
        text="Основное меню 2:",
        chat_id=chat_id,
        message_id=menu2_id,
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            tak,                # <<< и сюда
            unit
        )
    )



async def back_to_main(call: CallbackQuery, state: FSMContext):
    # Возвращаемся в главное меню
    await state.clear()
    unit = await get_unit(call.message.chat.id)
    tax  = await get_tax(call.message.chat.id)
    fix  = await get_measurement_fix(call.message.chat.id)
    km   = await get_measurement_km(call.message.chat.id)
    await call.message.edit_text(
        "Привет! Настройте параметры:",
        reply_markup=main_menu(unit, tax, fix, km)
    )
    await call.answer()

# ─── 6.1) Переход в ввод конкретной строки меню 2 ─────────────
async def menu2_item_menu(call: CallbackQuery, state: FSMContext):
    # Определяем, какая кнопка нажата: countertop, wall, boil, sink, glue или edges
    key = call.data  # «menu2_countertop» и т. д.
    await state.set_state(Settings.menu2_item)
    await state.update_data(menu2_item_key=key, menu2_message_id=call.message.message_id)
    # Формируем текст запроса и единицу
    label, unit_type = {
        "menu2_countertop":("Столешница", "м2"),
        "menu2_wall":      ("Стеновая",   "м2"),
        "menu2_boil":      ("Вырез варка", "шт"),
        "menu2_sink":      ("Вырез мойка", "шт"),
        "menu2_glue":      ("Подклейка",   "шт"),
        "menu2_edges":     ("Бортики",     "м2"),
    }[key]
    await call.message.edit_text(f"Введите значение для {label} ({unit_type}):")
    await call.answer()

# ─── 6.2) Обработка ввода текста для одной из шести строк ────
async def menu2_item_input(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data["menu2_item_key"]          # «menu2_countertop» и т. д.
    menu2_id = data["menu2_message_id"]
    text = message.text.strip()

    # 1) Определяем, для какого ключа ввод:
    #    - «Столешница», «Стеновая», «Бортики» → разрешаем десятичные через запятую (например, "2,3").
    #      Фактически, эти ключи: "menu2_countertop", "menu2_wall", "menu2_edges".
    #    - Для остальных ("menu2_boil", "menu2_sink", "menu2_glue") → только целые (без запятой).

    if key in {"menu2_countertop", "menu2_wall", "menu2_edges"}:
        # Проверяем, что введена дробь через запятую (ровно одна запятая, обе части — цифры).
        parts = text.split(",")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            return await message.reply(
                "Неверный формат. Для дробей используйте запятую, например: 2,3 или 5,0"
            )
        # После этой проверки у нас гарантирован формат «X,Y», где X и Y — цифры/числа.
    else:
        # Ключ — один из {"menu2_boil","menu2_sink","menu2_glue"} → только целые
        if not text.isdigit():
            return await message.reply("Неверный формат. Введите целое число, например: 5")

    # 2) Заменяем запятую на точку перед сохранением (чтобы в БД хранилось "2.3" вместо "2,3")
    to_store = text.replace(",", ".")

    # 3) Выбираем нужную функцию-сеттер и сохраняем в БД
    setter = {
        "menu2_countertop": set_menu2_countertop,
        "menu2_wall":       set_menu2_wall,
        "menu2_boil":       set_menu2_boil,
        "menu2_sink":       set_menu2_sink,
        "menu2_glue":       set_menu2_glue,
        "menu2_edges":      set_menu2_edges,
    }[key]
    await setter(message.chat.id, to_store)

    # 4) Удаляем сообщение пользователя
    await message.delete()

    # 5) Возвращаемся в menu2, подгружая все шесть значений и остальные параметры заново
    await state.set_state(Settings.menu2)
    current_stone = await get_general_stone_type(message.chat.id)
    current_price = await get_price_per_meter(message.chat.id)
    unit = await get_unit(message.chat.id)
    cntp = await get_menu2_countertop(message.chat.id)
    wal  = await get_menu2_wall(message.chat.id)
    bo   = await get_menu2_boil(message.chat.id)
    si   = await get_menu2_sink(message.chat.id)
    gl   = await get_menu2_glue(message.chat.id)
    ed   = await get_menu2_edges(message.chat.id)
    tak = await get_menu2_takelage(message.chat.id)

    await message.bot.edit_message_text(
        text="Основное меню 2:",
        chat_id=message.chat.id,
        message_id=menu2_id,
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed, tak,
            unit
        )
    )

async def menu2_takelage_input(call: CallbackQuery, state: FSMContext):
    choice = "да" if call.data == "takel_yes" else "нет"
    chat_id = call.message.chat.id

    # Сохраняем выбор
    await set_menu2_takelage(chat_id, choice)

    # Возвращаем FSM в состояние Settings.menu2
    data = await state.get_data()
    menu2_id = data["menu2_message_id"]
    await state.set_state(Settings.menu2)

    # Повторно читаем все поля, включая только что установленный takelage
    current_stone  = await get_general_stone_type(chat_id)
    current_price  = await get_price_per_meter(chat_id)
    unit           = await get_unit(chat_id)
    cntp = await get_menu2_countertop(chat_id)
    wal  = await get_menu2_wall(chat_id)
    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_edges(chat_id)
    tak  = choice  # «да» или «нет»

    # Перерисовываем меню 2
    await call.message.edit_text(
        "Основное меню 2:",
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            tak,
            unit
        )
    )
    await call.answer(f"Такелаж: {choice}")


# ─── где-то после всех существующих хендлеров (но до запуска dp.start_polling) ───
# ─── Объединённый хендлер «Рассчитать» ───────────────────────────
async def calculate_handler(call: CallbackQuery, state: FSMContext):
    chat_id = call.message.chat.id
    unit = await get_unit(chat_id)  # "м2" или "м/п"

    # ─── 1) Расчёт стоимости материала ────────────────────────────
    price_str = await get_price_per_meter(chat_id)       # строка, например "5000" или "не указано"
    cntp_str  = await get_menu2_countertop(chat_id)      # строка, например "2.30" или "не указано"
    wall_str  = await get_menu2_wall(chat_id)            # строка, например "1.50" или "не указано"

    def to_float(x: str) -> float:
        return float(x.replace(",", ".")) if x not in ("не указано", "") else 0.0

    price = to_float(price_str)
    cntp  = to_float(cntp_str)
    wall  = to_float(wall_str)

    cost_cntp     = price * cntp
    cost_wall     = price * wall
    material_cost = cost_cntp + cost_wall

    def fmt_num(v: float) -> str:
        # если целое, без десятичной части; иначе — через запятую с двумя знаками
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{round(v,2):.2f}".replace(".", ",")

    material_log = [
        "📋 Расчёт стоимости материала:\n",
        f"• Цена за метр: {fmt_num(price)} ₽/{unit}",
        f"• Столешница: {cntp_str.replace('.',',')} {unit} × {fmt_num(price)} ₽ = {fmt_num(cost_cntp)} ₽",
        f"• Стеновая:    {wall_str.replace('.',',')} {unit} × {fmt_num(price)} ₽ = {fmt_num(cost_wall)} ₽",
        "─────────────────────────",
        f"Итого материал: {fmt_num(material_cost)} ₽"
    ]
    # заменяем текст меню 3 на лог материала
    await call.message.edit_text("\n".join(material_log))

    # ─── 2) Расчёт ЗП мастера ───────────────────────────────────────
    # 2.1) Какой камень
    stone_text = await get_general_stone_type(chat_id)  # "акрил" или "кварц"
    stone_key = "acryl" if stone_text == "акрил" else "quartz"

    # 2.2) Считаем прайс мастера из БД
    raw_price_ctp   = await get_master_salary(chat_id, f"master_{stone_key}_countertop")
    raw_price_wall  = await get_master_salary(chat_id, f"master_{stone_key}_wall")
    raw_price_boil  = await get_master_salary(chat_id, f"master_{stone_key}_boil")
    raw_price_sink  = await get_master_salary(chat_id, f"master_{stone_key}_sink")
    raw_price_glue  = await get_master_salary(chat_id, f"master_{stone_key}_glue")
    raw_price_edges = await get_master_salary(chat_id, f"master_{stone_key}_edges")

    def to_float_zero(s: str) -> float:
        s2 = s.replace(",", ".")
        return float(s2) if s2.replace(".", "", 1).isdigit() else 0.0

    price_ctp   = to_float_zero(raw_price_ctp)
    price_wall  = to_float_zero(raw_price_wall)
    price_boil  = to_float_zero(raw_price_boil)
    price_sink  = to_float_zero(raw_price_sink)
    price_glue  = to_float_zero(raw_price_glue)
    price_edges = to_float_zero(raw_price_edges)

    # 2.3) Пользовательские величины из меню 2
    raw_val_ctp   = await get_menu2_countertop(chat_id)  # "2.30" или "не указано"
    raw_val_wall  = await get_menu2_wall(chat_id)
    raw_val_boil  = await get_menu2_boil(chat_id)
    raw_val_sink  = await get_menu2_sink(chat_id)
    raw_val_glue  = await get_menu2_glue(chat_id)
    raw_val_edges = await get_menu2_edges(chat_id)

    def parse_area(v: str) -> float:
        return float(v) if v.replace(".", "", 1).isdigit() else 0.0

    def parse_count(v: str) -> int:
        return int(v) if v.isdigit() else 0

    val_ctp   = parse_area(raw_val_ctp)
    val_wall  = parse_area(raw_val_wall)
    val_edges = parse_area(raw_val_edges)
    val_boil  = parse_count(raw_val_boil)
    val_sink  = parse_count(raw_val_sink)
    val_glue  = parse_count(raw_val_glue)

    # 2.4) Считаем по каждому пункту
    cost_ctp   = price_ctp * val_ctp
    cost_wall  = price_wall * val_wall
    cost_boil  = price_boil * val_boil
    cost_sink  = price_sink * val_sink
    cost_glue  = price_glue * val_glue
    cost_edges = price_edges * val_edges

    total_master = cost_ctp + cost_wall + cost_boil + cost_sink + cost_glue + cost_edges

    # 2.5) Собираем лог для мастера
    def disp(v: str) -> str:
        return v.replace(".", ",") if v not in ("не указано", "") else "0"

    def fmt_price(p: float) -> str:
        return str(int(p)) if abs(p - round(p)) < 1e-9 else f"{round(p,2):.2f}".replace(".", ",")

    def fmt_cost(p: float) -> str:
        return str(int(p)) if abs(p - round(p)) < 1e-9 else f"{round(p,2):.2f}".replace(".", ",")

    master_log = [
        "\n📋 Расчёт ЗП мастера (тип камня: " + stone_text + "):\n",
        f"• Столешница:\n"
        f"    цена мастера за {unit} = {fmt_price(price_ctp)} ₽, "
        f"площадь = {disp(raw_val_ctp)} {unit} → "
        f"{fmt_price(price_ctp)} × {disp(raw_val_ctp)} = {fmt_cost(cost_ctp)} ₽\n",
        f"• Стеновая:\n"
        f"    цена мастера за {unit} = {fmt_price(price_wall)} ₽, "
        f"площадь = {disp(raw_val_wall)} {unit} → "
        f"{fmt_price(price_wall)} × {disp(raw_val_wall)} = {fmt_cost(cost_wall)} ₽\n",
        f"• Вырез варка:\n"
        f"    цена мастера за шт = {fmt_price(price_boil)} ₽, "
        f"количество = {val_boil} шт → "
        f"{fmt_price(price_boil)} × {val_boil} = {fmt_cost(cost_boil)} ₽\n",
        f"• Вырез мойка:\n"
        f"    цена мастера за шт = {fmt_price(price_sink)} ₽, "
        f"количество = {val_sink} шт → "
        f"{fmt_price(price_sink)} × {val_sink} = {fmt_cost(cost_sink)} ₽\n",
        f"• Подклейка:\n"
        f"    цена мастера за шт = {fmt_price(price_glue)} ₽, "
        f"количество = {val_glue} шт → "
        f"{fmt_price(price_glue)} × {val_glue} = {fmt_cost(cost_glue)} ₽\n",
        f"• Бортики:\n"
        f"    цена мастера за {unit} = {fmt_price(price_edges)} ₽, "
        f"длина = {disp(raw_val_edges)} {unit} → "
        f"{fmt_price(price_edges)} × {disp(raw_val_edges)} = {fmt_cost(cost_edges)} ₽\n",
        "────────────────────────────────\n",
        f"Итого ЗП мастера: {fmt_cost(total_master)} ₽"
    ]

    # ─── 3) Расчёт ЗП монтажника ────────────────────────────────────
    # 3.1) Смотрим тот же stone_key ("acryl" или "quartz")
    #     Поля в БД: installer_{stone_key}_countertop, installer_{stone_key}_wall,
    #                installer_{stone_key}_delivery, installer_{stone_key}_takelage
    raw_inst_ctp = await get_salary(chat_id, f"installer_{stone_key}_countertop")
    raw_inst_wall = await get_salary(chat_id, f"installer_{stone_key}_wall")
    raw_inst_deliv = await get_salary(chat_id, f"installer_{stone_key}_delivery")
    raw_inst_takel = await get_salary(chat_id, f"installer_{stone_key}_takelage")

    price_inst_ctp = to_float_zero(raw_inst_ctp)
    price_inst_wall = to_float_zero(raw_inst_wall)
    price_inst_deliv = to_float_zero(raw_inst_deliv)
    price_inst_takel = to_float_zero(raw_inst_takel)

    # Количества/площади те же, что для мастера:
    # val_ctp, val_wall (float), val_boil, val_sink, val_glue, val_edges
    # Но монтажнику нужны только столешница и стеновая (для него “boil/sink/glue/edges” не в счёт).
    cost_inst_ctp = price_inst_ctp * val_ctp
    cost_inst_wall = price_inst_wall * val_wall

    # Доставка — в любом случае прибавляем
    cost_inst_delivery = price_inst_deliv

    # Такелаж: смотрим флаг из БД (menu2_takelage: "да"/"нет")
    raw_takel_flag = await get_menu2_takelage(chat_id)  # "да"/"нет"/"не указано"
    takelage_cost = 0.0
    if raw_takel_flag == "да":
        # если пользователь выбрал «да», тогда считаем:
        # (площадь столешницы + площадь стеновой) × цена монтажника за takelage
        takelage_cost = price_inst_takel * (val_ctp + val_wall)

    total_inst = cost_inst_ctp + cost_inst_wall + cost_inst_delivery + takelage_cost

    inst_log = [
        "\n📋 Расчёт ЗП монтажника (тип камня: " + stone_text + "):\n",
        f"• Столешница:\n"
        f"    цена монтажника за {unit} = {fmt_price(price_inst_ctp)} ₽, "
        f"площадь = {disp(raw_val_ctp)} {unit} → "
        f"{fmt_price(price_inst_ctp)} × {disp(raw_val_ctp)} = {fmt_cost(cost_inst_ctp)} ₽\n",
        f"• Стеновая:\n"
        f"    цена монтажника за {unit} = {fmt_price(price_inst_wall)} ₽, "
        f"площадь = {disp(raw_val_wall)} {unit} → "
        f"{fmt_price(price_inst_wall)} × {disp(raw_val_wall)} = {fmt_cost(cost_inst_wall)} ₽\n",
        f"• Доставка:\n"
        f"    фиксированная сумма = {fmt_price(price_inst_deliv)} ₽\n",
    ]

    if raw_takel_flag == "да":
        inst_log += [
            f"• Такелаж:\n"
            f"    цена монтажника за {unit} = {fmt_price(price_inst_takel)} ₽, "
            f"суммарная длина = {disp(raw_val_ctp)} + {disp(raw_val_wall)} = {fmt_num(val_ctp + val_wall)} {unit} → "
            f"{fmt_price(price_inst_takel)} × {fmt_num(val_ctp + val_wall)} = {fmt_cost(takelage_cost)} ₽\n"
        ]
    else:
        inst_log += [f"• Такелаж: нет → 0 ₽\n"]

    inst_log += [
        "────────────────────────────────\n",
        f"Итого ЗП монтажника: {fmt_cost(total_inst)} ₽"
    ]

    # ─── 4) Расчёт стоимости замеров ────────────────────────────────
    raw_meas_fix = await get_measurement_fix(chat_id)  # строка, напр. "3000" или "не указано"
    raw_meas_km = await get_measurement_km(chat_id)  # строка, напр. "20" или "не указано"
    raw_km_qty = await get_menu3_km(chat_id)  # строка, напр. "10" или "не указано"

    meas_fix = to_float_zero(raw_meas_fix)
    meas_km = to_float_zero(raw_meas_km)
    # количество километров — целое число
    km_qty = int(raw_km_qty) if raw_km_qty.isdigit() else 0

    cost_meas_km = meas_km * km_qty
    total_meas = meas_fix + cost_meas_km

    measurement_log = [
        "\n📋 Расчёт стоимости замеров:\n",
        f"• Фиксированная стоимость выезда = {fmt_num(meas_fix)} ₽",
        f"• {km_qty} км × {fmt_num(meas_km)} ₽/км = {fmt_num(cost_meas_km)} ₽",
        "─────────────────────────",
        f"Итого замеры: {fmt_num(total_meas)} ₽"
    ]
    await call.message.answer("\n".join(measurement_log))

    # ─── 5) Расчёт себестоимости ───────────────────────────────────
    total_cost_price = material_cost + total_master + total_inst + total_meas

    cost_price_log = [
        "\n📍 Себестоимость (итог):\n",
        f"• Итого материал     = {fmt_num(material_cost)} ₽",
        f"• Итого ЗП мастера   = {fmt_cost(total_master)} ₽",
        f"• Итого ЗП монтажника = {fmt_cost(total_inst)} ₽",
        f"• Итого замеры       = {fmt_num(total_meas)} ₽",
        "─────────────────────────",
        f"Себестоимость: {fmt_num(total_cost_price)} ₽"
    ]

    # ─── 6) Итоговая стоимость для клиента ─────────────────────────
    # читаем проценты: маржа, МОП (menu3_mop), налог из меню 1
    raw_margin = await get_menu3_margin(chat_id)  # строка, напр. "15" или "не указано"
    raw_mop = await get_menu3_mop(chat_id)  # строка, напр. "5" или "не указано"
    raw_tax = await get_tax(chat_id)  # строка, напр. "13" или "не указано"

    # преобразуем к float, если не указано — 0
    margin = float(raw_margin) if raw_margin.isdigit() else 0.0
    mop = float(raw_mop) if raw_mop.isdigit() else 0.0
    tax = float(raw_tax) if raw_tax.isdigit() else 0.0

    total_pct = margin + mop + tax  # суммарный %
    # защищаемся от деления на ноль
    if total_pct >= 100:
        client_price_log = [
            "\n❗ Ошибка: сумма процентов (маржа + МОП + налог) ≥ 100%.",
            f"Получилось: маржа={fmt_num(margin)}%, МОП={fmt_num(mop)}%, налог={fmt_num(tax)}% → сумма={fmt_num(total_pct)}%",
            "Невозможно рассчитать итоговую стоимость для клиента."
        ]
    else:
        # итоговая цена для клиента:
        # client_price = total_cost_price * 100 / (100 − total_pct)
        client_price = total_cost_price * 100.0 / (100.0 - total_pct)

        def fmt_client(v: float) -> str:
            return str(int(v)) if abs(v - round(v)) < 1e-9 else f"{round(v, 2):.2f}".replace(".", ",")

        client_price_log = [
            "\n💰 Итоговая стоимость для клиента:\n",
            f"• Себестоимость = {fmt_num(total_cost_price)} ₽",
            f"• Сумма %: маржа {fmt_num(margin)}% + МОП {fmt_num(mop)}% + налог {fmt_num(tax)}% = {fmt_num(total_pct)}%",
            "─────────────────────────",
            f"Итого клиент: {fmt_client(client_price)} ₽"
        ]

    # ——— проверка введённой маржи ———
    implied_total_pct = (client_price - total_cost_price) / client_price * 100
    implied_margin = implied_total_pct - (mop + tax)
    # округлим до сотых
    if abs(implied_margin - margin) < 0.01:
        verification_log = f"✅ Маржа подтверждена: {round(implied_margin, 2):.2f}% соответствует введённой {round(margin, 2):.2f}%."
    else:
        verification_log = (
            f"❗ Расхождение маржи: рассчитано {round(implied_margin, 2):.2f}%, "
            f"а введено {round(margin, 2):.2f}%."
        )


    await call.message.answer("\n".join(master_log))
    await call.message.answer("\n".join(inst_log))
    await call.message.answer("\n".join(cost_price_log))
    await call.answer()

    await call.message.answer("\n".join(client_price_log))
    await call.message.answer(verification_log)


# ─── (где-то после всех определений menu3_* и перед dp.start_polling) ─────────────────────────────────────

# ─── 6) Запуск бота ────────────────────────────────────────────
async def main():
    await init_db()

    bot = Bot(token=API_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрация хендлеров
    dp.message.register(start_handler, CommandStart())

    dp.callback_query.register(set_unit_menu, lambda c: c.data == "set_unit")
    dp.callback_query.register(unit_choice,   lambda c: c.data in ("unit_m2", "unit_mp"))

    dp.callback_query.register(set_tax_menu,   lambda c: c.data == "set_tax_system")
    dp.message.register     (tax_input, Settings.tax)

    # ─── вставьте регистрацию measurement ─────────────
    dp.callback_query.register(set_measurement_menu, lambda c: c.data == "set_measurement_cost")
    dp.callback_query.register(meas_fix_menu, lambda c: c.data == "meas_fix")
    dp.callback_query.register(meas_km_menu, lambda c: c.data == "meas_km")
    dp.callback_query.register(meas_back, lambda c: c.data == "meas_back")
    dp.message.register(meas_fix_input, Settings.meas_fix)
    dp.message.register(meas_km_input, Settings.meas_km)
    # dp.callback_query.register(set_master_menu, lambda c: c.data == "set_master_salary")
    # dp.callback_query.register(master_type_choice, lambda c: c.data in ("master_acryl", "master_quartz"))
    # dp.callback_query.register(master_type_back, lambda c: c.data == "master_back")
    # dp.callback_query.register(master_input_menu, lambda c: "_" in c.data and c.data.startswith(("acryl_", "quartz_")))
    # dp.message.register(master_input_handler, Settings.master_input)
    dp.callback_query.register(salary_role_menu,    lambda c: c.data in ("salary_master","salary_installer"))
    dp.callback_query.register(salary_stone_choice, lambda c: c.data.startswith("salary_") and len(c.data.split("_"))==3)
    dp.callback_query.register(salary_stone_back, lambda c: c.data.endswith("_stone_back"))
    dp.callback_query.register(
        salary_item_menu,
        lambda c: (
                c.data.startswith("salary_") and
                c.data.split("_")[-1] in {
                    "countertop", "wall", "boil", "sink", "glue", "edges",
                    "delivery", "takelage"
                }
        )
    )
    dp.message.register     (salary_item_input,     Settings.salary_item)
    # ─── Регистрация для меню 2 ─────────────────────────────
    dp.callback_query.register(to_menu2, lambda c: c.data == "to_menu2")
    dp.callback_query.register(first_stone_choice, lambda c: c.data == "set_first_stone")
    dp.callback_query.register(stone2_selected, lambda c: c.data in ("stone2_acryl", "stone2_quartz"))
    dp.callback_query.register(price_meter_menu, lambda c: c.data == "set_price_meter")
    dp.message.register(price_meter_input, Settings.price_meter)
    dp.callback_query.register(back_to_main, lambda c: c.data == "back_to_main")
    # ─── регистрируем шесть новых пунктов menu2 ──────────────
    dp.callback_query.register(menu2_item_menu, lambda c: c.data in {"menu2_countertop", "menu2_wall", "menu2_boil", "menu2_sink", "menu2_glue", "menu2_edges"})
    dp.message.register(menu2_item_input, Settings.menu2_item)

    # ─── Регистрация для меню 3 ─────────────────────────────
    dp.callback_query.register(to_menu3, lambda c: c.data == "to_menu3")
    dp.callback_query.register(menu3_km_menu, lambda c: c.data == "menu3_km")
    dp.callback_query.register(menu3_mop_menu, lambda c: c.data == "menu3_mop")
    dp.callback_query.register(menu3_margin_menu, lambda c: c.data == "menu3_margin")
    dp.callback_query.register(back_to_menu2, lambda c: c.data == "back_to_menu2")
    dp.message.register(menu3_km_input, Settings.menu3_km)
    dp.message.register(menu3_mop_input, Settings.menu3_mop)
    dp.message.register(menu3_margin_input, Settings.menu3_margin)

    # ─── Регистрируем обработчик «Рассчитать» ─────────────────────
    dp.callback_query.register(calculate_handler, lambda c: c.data == "calculate")
    dp.callback_query.register(menu2_takelage_menu, lambda c: c.data == "menu2_takelage")
    dp.callback_query.register(menu2_takelage_input, lambda c: c.data in {"takel_yes", "takel_no"})

    # ─── (где-то после всех определений menu3_* и перед dp.start_polling) ─────────────────────────────────────

    # Регистрируем кнопку «Рассчитать»
    # dp.callback_query.register(calculate_master_salary, lambda c: c.data == "calculate")

    # ─── (далее идёт await dp.start_polling(bot)) ──────────────────────────────────────────────────────────

    # ─── после этой строки идёт await dp.start_polling(bot) ───

    # Запускаем long-polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
