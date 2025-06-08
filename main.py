#API_TOKEN = "7908411125:AAFxJdhRYxke3mLVRa4Gxxy1Ow2dNk4Sf5w"

import asyncio
from db import connection, close_db

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.exceptions import TelegramBadRequest

API_TOKEN = "7908411125:AAFxJdhRYxke3mLVRa4Gxxy1Ow2dNk4Sf5w"


async def safe_edit_message_text(func, *args, **kwargs):
    """Edit message text and ignore 'message is not modified' errors."""
    try:
        await func(*args, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise



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
    stone_price = State()  # ввод «Цена за камень» на меню 2
    menu2_item = State()  # для ввода Столешница/Стеновая/…/Бортики
    menu2_item_unit = State()  # выбор единицы (м2 или м/п) для пункта меню 2
    countertop_menu = State()  # подменю столешницы с выбором м2/м/п
    countertop_input = State()  # ввод значения для конкретной единицы
    wall_menu = State()  # подменю стеновой с выбором м2/м/п
    wall_input = State()  # ввод значения стеновой для выбранной единицы

    menu3_takelage = State()  # состояние выбора «такелаж» в логистике
    # ─── добавляем подменю 3 ────────────────────────────────
    menu3 = State()  # сам экран «меню 3»
    menu3_km = State()  # ввод «Сколько КМ?»
    menu3_mop = State()  # ввод «проценты МОПу»
    menu3_margin = State()  # ввод «маржа»

    tax_stone    = State()  # выбор камня для налогов
    mop_stone    = State()  # выбор камня для МОП
    margin_stone = State()  # выбор камня для маржи


# ─── 2) Инициализация базы ────────────────────────────────────
async def init_db():
    async with connection() as db:
        # 1) Создаём основную таблицу (unit + tax_percent)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                chat_id                   INTEGER PRIMARY KEY,
                unit                      TEXT    DEFAULT 'не выбрано',
                tax_percent               TEXT    DEFAULT 'не указано',

                tax_percent_quartz        TEXT    DEFAULT 'не указано',
                tax_percent_acryl         TEXT    DEFAULT 'не указано',
                mop_percent_quartz        TEXT    DEFAULT 'не указано',
                mop_percent_acryl         TEXT    DEFAULT 'не указано',
                margin_percent_quartz     TEXT    DEFAULT 'не указано',
                margin_percent_acryl      TEXT    DEFAULT 'не указано',

                measurement_fix           TEXT    DEFAULT 'не указано',
                measurement_km            TEXT    DEFAULT 'не указано',
                master_unit               TEXT    DEFAULT 'не выбрано',
                installer_unit            TEXT    DEFAULT 'не выбрано',
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

        # 2a) Добавляем новые колонки для налогов, МОП и маржи по типам камня
        for col in (
            "tax_acryl", "tax_quartz",
            "mop_acryl", "mop_quartz",
            "margin_acryl", "margin_quartz",
        ):
            if col not in cols:
                await db.execute(
                    f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'"
                )

        # 3) Обязательно добавляем measurement-колонки
        for col in ("measurement_fix", "measurement_km"):
            if col not in cols:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'")

        # 3a) Колонки единиц для ЗП мастера и монтажника
        for col in ("master_unit", "installer_unit"):
            if col not in cols:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не выбрано'")

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
            "installer_acryl_delivery", "installer_acryl_delivery_km", "installer_acryl_takelage",
            "installer_quartz_countertop", "installer_quartz_wall",
            "installer_quartz_delivery", "installer_quartz_delivery_km", "installer_quartz_takelage",
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
        if "stone_price" not in cols:
            await db.execute("ALTER TABLE user_settings ADD COLUMN stone_price TEXT DEFAULT 'не указано'")

        # ─── меню 2: шесть полей для ручного ввода ─────────────────
        for col in (
            "menu2_countertop", "menu2_wall", "menu2_boil",
            "menu2_sink", "menu2_glue", "menu2_edges",
        ):
            if col not in cols:
                await db.execute(
                    f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'"
                )

        # дополнительные поля для хранения значений в м2 и м/п отдельно
        for col in (
            "menu2_countertop_m2", "menu2_countertop_mp",
            "menu2_wall_m2", "menu2_wall_mp",
            "menu2_edges_m2", "menu2_edges_mp",
        ):
            if col not in cols:
                await db.execute(
                    f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'"
                )

        # *** ДОБАВЛЯЕМ новую колонку для Такелаж ***
        if "menu2_takelage" not in cols:
            await db.execute("ALTER TABLE user_settings ADD COLUMN menu2_takelage TEXT DEFAULT 'не указано'")

        # ─── добавляем колонки для меню 3 ────────────────────────
        for col in ("menu3_km", "menu3_mop", "menu3_margin"):
            if col not in cols:
                await db.execute(
                    f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'"
                )


        # ─── новые колонки для процентов по камню ───────────────
        pct_cols = [
            "tax_percent_quartz", "tax_percent_acryl",
            "mop_percent_quartz", "mop_percent_acryl",
            "margin_percent_quartz", "margin_percent_acryl",

        ]
        for col in pct_cols:
            if col not in cols:
                await db.execute(
                    f"ALTER TABLE user_settings ADD COLUMN {col} TEXT DEFAULT 'не указано'"
                )


        # дополнительные колонки для налогов/МОП/маржи по камням
        for col in (
            "tax_acryl", "tax_quartz",
            "mop_acryl", "mop_quartz",
            "margin_acryl", "margin_quartz",
        ):
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


async def get_master_unit(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT master_unit FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не выбрано"


async def set_master_unit(chat_id: int, value: str):
    async with connection() as db:
        await db.execute(
            """
            INSERT INTO user_settings(chat_id, master_unit)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET master_unit = excluded.master_unit
            """,
            (chat_id, value),
        )
        await db.commit()


async def get_installer_unit(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute("SELECT installer_unit FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не выбрано"


async def set_installer_unit(chat_id: int, value: str):
    async with connection() as db:
        await db.execute(
            """
            INSERT INTO user_settings(chat_id, installer_unit)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET installer_unit = excluded.installer_unit
            """,
            (chat_id, value),
        )
        await db.commit()


async def get_tax(chat_id: int) -> str:
    quartz = await get_tax_value(chat_id, "quartz")
    acryl  = await get_tax_value(chat_id, "acryl")
    return f"кварц {quartz}% | акрил {acryl}%"


async def set_tax(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, tax_percent)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET tax_percent = excluded.tax_percent
        """, (chat_id, value))
        await db.commit()

async def get_tax_percent(chat_id: int, stone: str) -> str:

    column = f"tax_percent_{stone}"

    async with connection() as db:
        cur = await db.execute(
            f"SELECT {column} FROM user_settings WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"


async def set_tax_percent(chat_id: int, stone: str, value: str):
    column = f"tax_percent_{stone}"

    async with connection() as db:
        await db.execute(
            f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column} = excluded.{column}
            """,
            (chat_id, value),
        )
        await db.commit()

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

async def get_stone_price(chat_id: int) -> str:
    async with connection() as db:
        cur = await db.execute(
            "SELECT stone_price FROM user_settings WHERE chat_id = ?", (chat_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

# ─── после set_stone_price ───────────────────────────────
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

# --- новые геттеры/сеттеры для значений в м2 и м/п ---
async def get_menu2_value(chat_id: int, key: str, unit: str) -> str:
    column = f"menu2_{key}_{'m2' if unit == 'м2' else 'mp'}"
    async with connection() as db:
        cur = await db.execute(f"SELECT {column} FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_menu2_value(chat_id: int, key: str, unit: str, value: str):
    column = f"menu2_{key}_{'m2' if unit == 'м2' else 'mp'}"
    async with connection() as db:
        await db.execute(
            f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column} = excluded.{column}
            """,
            (chat_id, value),
        )
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

async def menu3_takelage_menu(call: CallbackQuery, state: FSMContext):
    # 1) Переводим FSM в состояние Settings.menu3_takelage
    await state.set_state(Settings.menu3_takelage)
    data = await state.get_data()
    await state.update_data(menu3_message_id=data["menu3_message_id"])

    # 2) Показываем юзеру две кнопки «Да» / «Нет»
    msg = await call.message.answer(
        "Такелаж: выберите «Да» или «Нет»:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да",  callback_data="takel_yes")],
            [InlineKeyboardButton(text="Нет", callback_data="takel_no")],
        ])
    )
    await state.update_data(prompt_id=msg.message_id)
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
    quartz = await get_mop_value(chat_id, "quartz")
    acryl  = await get_mop_value(chat_id, "acryl")
    return f"кварц {quartz}% | акрил {acryl}%"

async def set_menu3_mop(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu3_mop)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu3_mop = excluded.menu3_mop
        """, (chat_id, value))
        await db.commit()

async def get_menu3_margin(chat_id: int) -> str:
    quartz = await get_margin_value(chat_id, "quartz")
    acryl  = await get_margin_value(chat_id, "acryl")
    return f"кварц {quartz}% | акрил {acryl}%"

async def set_menu3_margin(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, menu3_margin)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET menu3_margin = excluded.menu3_margin
        """, (chat_id, value))
        await db.commit()


async def get_mop_percent(chat_id: int, stone: str) -> str:
    column = f"mop_percent_{stone}"
    async with connection() as db:
        cur = await db.execute(
            f"SELECT {column} FROM user_settings WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_mop_percent(chat_id: int, stone: str, value: str):
    column = f"mop_percent_{stone}"

    async with connection() as db:
        await db.execute(
            f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column} = excluded.{column}
            """,
            (chat_id, value),
        )
        await db.commit()


async def get_margin_percent(chat_id: int, stone: str) -> str:
    column = f"margin_percent_{stone}"
    async with connection() as db:
        cur = await db.execute(
            f"SELECT {column} FROM user_settings WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_margin_percent(chat_id: int, stone: str, value: str):
    column = f"margin_percent_{stone}"

    async with connection() as db:
        await db.execute(
            f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column} = excluded.{column}
            """,
            (chat_id, value),
        )
        await db.commit()

async def get_tax_value(chat_id: int, stone: str) -> str:
    column = f"tax_{stone}"
    async with connection() as db:
        cur = await db.execute(
            f"SELECT {column} FROM user_settings WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_tax_value(chat_id: int, stone: str, value: str):
    column = f"tax_{stone}"
    async with connection() as db:
        await db.execute(
            f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column} = excluded.{column}
            """,
            (chat_id, value),
        )
        await db.commit()

async def get_mop_value(chat_id: int, stone: str) -> str:
    column = f"mop_{stone}"
    async with connection() as db:
        cur = await db.execute(
            f"SELECT {column} FROM user_settings WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_mop_value(chat_id: int, stone: str, value: str):
    column = f"mop_{stone}"
    async with connection() as db:
        await db.execute(
            f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column} = excluded.{column}
            """,
            (chat_id, value),
        )
        await db.commit()

async def get_margin_value(chat_id: int, stone: str) -> str:
    column = f"margin_{stone}"
    async with connection() as db:
        cur = await db.execute(
            f"SELECT {column} FROM user_settings WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else "не указано"

async def set_margin_value(chat_id: int, stone: str, value: str):
    column = f"margin_{stone}"
    async with connection() as db:
        await db.execute(
            f"""
            INSERT INTO user_settings(chat_id, {column})
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {column} = excluded.{column}
            """,
            (chat_id, value),
        )
        await db.commit()

# ─── далее продолжается остальной код ────────────────────────

async def set_stone_price(chat_id: int, value: str):
    async with connection() as db:
        await db.execute("""
            INSERT INTO user_settings(chat_id, stone_price)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET stone_price = excluded.stone_price
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

def _display_pct(value: str) -> str:
    return value if "%" in value else f"{value}%"


def main_menu(
    tax_value: str,
    fix_value: str,
    km_value: str,
    mop_value: str,
    margin_value: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ЗП Мастера", callback_data="salary_master")],
            [InlineKeyboardButton(text="ЗП Монтажника", callback_data="salary_installer")],
            [
                InlineKeyboardButton(
                    text=f"Система налогов | {_display_pct(tax_value)}",
                    callback_data="set_tax_system",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Стоимость замеров | Фикс {fix_value} | КМ {km_value}",
                    callback_data="set_measurement_cost",
                )
            ],
            [InlineKeyboardButton(text=f"МОП | {_display_pct(mop_value)}", callback_data="set_mop")],
            [InlineKeyboardButton(text=f"Маржа | {_display_pct(margin_value)}", callback_data="set_margin")],
            [InlineKeyboardButton(text="Просчёт изделия", callback_data="to_menu2")],
        ]
    )


def meas_submenu(fix: str, km: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Фикс | {fix}",        callback_data="meas_fix"),
            InlineKeyboardButton(text=f"Стоимость КМ | {km}", callback_data="price_inst_deliv_km"),
        ],
        [InlineKeyboardButton(text="← Назад", callback_data="meas_back")],
    ])

def countertop_submenu(m2_val: str, mp_val: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"м2 | {m2_val}", callback_data="counter_m2"),
            InlineKeyboardButton(text=f"м/п | {mp_val}", callback_data="counter_mp"),
        ],
        [InlineKeyboardButton(text="← Назад", callback_data="counter_back")],
    ])

def wall_submenu(m2_val: str, mp_val: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"м2 | {m2_val}", callback_data="wall_m2"),
            InlineKeyboardButton(text=f"м/п | {mp_val}", callback_data="wall_mp"),
        ],
        [InlineKeyboardButton(text="← Назад", callback_data="wall_back")],
    ])

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
            InlineKeyboardButton(text=f"Бортики | {values['edges']} | м/п", callback_data=f"salary_{role}_{stone}_edges")
        ]]
    else:  # installer
        kb += [[
            InlineKeyboardButton(text=f"Столешница | {values['countertop']} | {unit}", callback_data=f"salary_{role}_{stone}_countertop")
        ],[
            InlineKeyboardButton(text=f"Стеновая | {values['wall']} | {unit}",       callback_data=f"salary_{role}_{stone}_wall")
        ],[
            InlineKeyboardButton(text=f"Доставка | фикс {values['delivery']} | км {values['delivery_km']}", callback_data=f"salary_{role}_{stone}_delivery"),
            InlineKeyboardButton(text=f"Такелаж | {values['takelage']} | {unit}",     callback_data=f"salary_{role}_{stone}_takelage")
        ]]
    kb.append([InlineKeyboardButton(text=f"Ед. измерения | {unit}", callback_data=f"salary_{role}_{stone}_unit")])
    kb.append([InlineKeyboardButton(text="← Назад", callback_data=f"salary_{role}_stone_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ─── Новый блок: меню 2 ──────────────────────────────────────
def menu2_kb(stone: str, price: str,
             cntp: str, wal: str, bo: str, si: str, gl: str, ed: str,
             unit: str) -> InlineKeyboardMarkup:
    """
    Теперь menu2_kb получает 9 аргументов:
    1) stone  – выбранный тип камня
    2) price  – цена за камень
    3) cntp   – Столешница
    4) wal    – Стеновая
    5) bo     – Вырез варка
    6) si     – Вырез мойка
    7) gl     – Подклейка
    8) ed     – Бортики
    9) unit  – единица измерения ("м2"/"м/п")
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Тип камня | {stone}",        callback_data="set_first_stone")],
        [InlineKeyboardButton(text=f"Цена за камень | {price}",   callback_data="set_stone_price")],
        [InlineKeyboardButton(text=f"Столешница | {cntp}", callback_data="menu2_countertop")],

        [InlineKeyboardButton(text=f"Стеновая | {wal}",   callback_data="menu2_wall")],

        [
          InlineKeyboardButton(text=f"Вырез варка | {bo} шт",      callback_data="menu2_boil"),
          InlineKeyboardButton(text=f"Вырез мойка | {si} шт",      callback_data="menu2_sink"),
        ],
        [
          InlineKeyboardButton(text=f"Подклейка | {gl} шт",         callback_data="menu2_glue"),
          InlineKeyboardButton(text=f"Бортики | {ed} | м/п",    callback_data="menu2_edges"),
        ],
        # далее оставшиеся кнопки:
        [InlineKeyboardButton(text="Логистика", callback_data="to_menu3")],
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_main")],
    ])


def first_stone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акрил",  callback_data="stone2_acryl")],
        [InlineKeyboardButton(text="Кварц",  callback_data="stone2_quartz")],
    ])


def menu3_kb(km: str, takel: str) -> InlineKeyboardMarkup:
    """Кнопки меню «Логистика»"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"КМ от МКАД | {km}", callback_data="menu3_km")],
        [InlineKeyboardButton(text=f"Такелаж | {takel}", callback_data="menu3_takelage")],
        [
            InlineKeyboardButton(text="← Назад", callback_data="back_to_menu2"),
            InlineKeyboardButton(text="Рассчитать", callback_data="calculate")
        ],
    ])

# ─── 5) Хендлеры ───────────────────────────────────────────────
async def start_handler(message: Message, state: FSMContext):
    # Сбросим любое текущее состояние
    await state.clear()

    tax_value = await get_tax(message.chat.id)
    mop_value = await get_menu3_mop(message.chat.id)
    margin_value = await get_menu3_margin(message.chat.id)

    fix = await get_measurement_fix(message.chat.id)
    km  = await get_measurement_km(message.chat.id)
    await message.answer(
        "Привет! Настройте параметры:",
        reply_markup=main_menu(tax_value, fix, km, mop_value, margin_value),
    )

# ─── Хендлеры меню 3 ─────────────────────────────────────────

async def to_menu3(call: CallbackQuery, state: FSMContext):
    # Переходим в состояние меню3
    await state.set_state(Settings.menu3)
    await state.update_data(menu3_message_id=call.message.message_id)

    km_current  = await get_menu3_km(call.message.chat.id)
    takel_current = await get_menu2_takelage(call.message.chat.id)

    await safe_edit_message_text(call.message.edit_text, 
        "Логистика:",
        reply_markup=menu3_kb(km_current, takel_current)
    )
    await call.answer()


async def menu3_km_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu3_km)
    data = await state.get_data()
    await state.update_data(menu3_message_id=data["menu3_message_id"])
    msg = await call.message.answer("Введите количество КМ (целое число):")
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def menu3_km_input(message: Message, state: FSMContext):
    data       = await state.get_data()
    menu3_id   = data.get("menu3_message_id")
    menu_id    = data.get("menu_message_id")
    prompt_id  = data.get("prompt_id")
    text       = message.text.strip()
    if not text.isdigit():
        return await message.reply("Неверный формат. Введите целое число, например: 10")
    await set_menu3_km(message.chat.id, text)
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    if menu3_id:
        await state.set_state(Settings.menu3)
        km_current  = await get_menu3_km(message.chat.id)
        takel_current = await get_menu2_takelage(message.chat.id)
        await safe_edit_message_text(message.bot.edit_message_text, 
            text="Логистика:",
            chat_id=message.chat.id,
            message_id=menu3_id,
            reply_markup=menu3_kb(km_current, takel_current)
        )
    else:
        await state.clear()
        tax  = await get_tax(message.chat.id)
        fix  = await get_measurement_fix(message.chat.id)
        km   = await get_measurement_km(message.chat.id)
        mop  = await get_menu3_mop(message.chat.id)
        margin = await get_menu3_margin(message.chat.id)
        await safe_edit_message_text(message.bot.edit_message_text, 
            text="Параметры:",
            chat_id=message.chat.id,
            message_id=menu_id,
            reply_markup=main_menu(tax, fix, km, mop, margin)
        )


async def menu3_mop_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu3_mop)
    data = await state.get_data()
    await state.update_data(menu3_message_id=data["menu3_message_id"])
    msg = await call.message.answer("Введите проценты МОПу (целое число от 0 до 100):")
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def menu3_mop_input(message: Message, state: FSMContext):
    data       = await state.get_data()
    menu3_id   = data.get("menu3_message_id")
    menu_id    = data.get("menu_message_id")
    prompt_id  = data.get("prompt_id")
    stone      = data.get("stone")
    text       = message.text.strip()
    if not text.isdigit() or not (0 <= int(text) <= 100):
        return await message.reply("Неверный формат. Введите целое число от 0 до 100.")
    if stone:
        await set_mop_value(message.chat.id, stone, text)
    else:
        await set_menu3_mop(message.chat.id, text)
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    if menu3_id:
        await state.set_state(Settings.menu3)
        km_current  = await get_menu3_km(message.chat.id)
        takel_current = await get_menu2_takelage(message.chat.id)
        await safe_edit_message_text(message.bot.edit_message_text, 
            text="Логистика:",
            chat_id=message.chat.id,
            message_id=menu3_id,
            reply_markup=menu3_kb(km_current, takel_current)
        )
    else:
        await state.clear()
        tax  = await get_tax(message.chat.id)
        fix  = await get_measurement_fix(message.chat.id)
        km   = await get_measurement_km(message.chat.id)
        mop  = await get_menu3_mop(message.chat.id)
        margin = await get_menu3_margin(message.chat.id)
        await safe_edit_message_text(message.bot.edit_message_text, 
            text="Параметры:",
            chat_id=message.chat.id,
            message_id=menu_id,
            reply_markup=main_menu(tax, fix, km, mop, margin)
        )


async def menu3_margin_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu3_margin)
    data = await state.get_data()
    await state.update_data(menu3_message_id=data.get("menu3_message_id"))
    msg = await call.message.answer(
        "Введите маржу в % (целое число от 0 до 100):"
    )
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def menu3_margin_input(message: Message, state: FSMContext):
    data       = await state.get_data()
    menu3_id   = data.get("menu3_message_id")
    menu_id    = data.get("menu_message_id")
    prompt_id  = data.get("prompt_id")
    stone      = data.get("stone")
    text       = message.text.strip()
    if not text.isdigit() or not (0 <= int(text) <= 100):
        return await message.reply("Неверный формат. Введите целое число от 0 до 100.")
    if stone:
        await set_margin_value(message.chat.id, stone, text)
    else:
        await set_menu3_margin(message.chat.id, text)
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    if menu3_id:
        await state.set_state(Settings.menu3)
        km_current = await get_menu3_km(message.chat.id)
        takel_current = await get_menu2_takelage(message.chat.id)
        await safe_edit_message_text(message.bot.edit_message_text, 
            text="Логистика:",
            chat_id=message.chat.id,
            message_id=menu3_id,
            reply_markup=menu3_kb(km_current, takel_current),
        )
    else:
        await state.clear()
        tax = await get_tax(message.chat.id)
        fix = await get_measurement_fix(message.chat.id)
        km = await get_measurement_km(message.chat.id)
        mop = await get_menu3_mop(message.chat.id)
        margin = await get_menu3_margin(message.chat.id)
        await safe_edit_message_text(message.bot.edit_message_text, 
            text="Параметры:",
            chat_id=message.chat.id,
            message_id=menu_id,
            reply_markup=main_menu(tax, fix, km, mop, margin),
        )


async def back_to_menu2(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu2)
    chat_id = call.message.chat.id
    data    = await state.get_data()
    menu2_id = data["menu2_message_id"]

    current_stone  = await get_general_stone_type(chat_id)
    current_price  = await get_stone_price(chat_id)
    unit           = await get_unit(chat_id)
    cntp_m2 = await get_menu2_value(chat_id, "countertop", "м2")
    cntp_mp = await get_menu2_value(chat_id, "countertop", "м/п")
    cntp = f"{cntp_m2} м2 | {cntp_mp} п/м"

    wal_m2 = await get_menu2_value(chat_id, "wall", "м2")
    wal_mp = await get_menu2_value(chat_id, "wall", "м/п")
    wal = f"{wal_m2} м2 | {wal_mp} п/м"

    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_value(chat_id, "edges", "м/п")
    await safe_edit_message_text(call.message.edit_text, 
        "Основное меню 2:",
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
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
    await safe_edit_message_text(call.message.edit_text, "Выберите единицу измерения:", reply_markup=kb)
    await call.answer()


async def unit_choice(call: CallbackQuery, state: FSMContext):
    choice = "м2" if call.data == "unit_m2" else "м/п"
    await set_unit(call.message.chat.id, choice)

    data = await state.get_data()
    menu_id = data.get("menu_message_id")

    # Снова получаем обе настройки и редактируем то же сообщение
    tax  = await get_tax(call.message.chat.id)
    fix = await get_measurement_fix(call.message.chat.id)
    km  = await get_measurement_km(call.message.chat.id)
    mop = await get_menu3_mop(call.message.chat.id)
    margin = await get_menu3_margin(call.message.chat.id)
    await safe_edit_message_text(call.message.bot.edit_message_text, 
        text="Параметры:",
        chat_id=call.message.chat.id,
        message_id=menu_id,
        reply_markup=main_menu(tax, fix, km, mop, margin)
    )
    await call.answer()


async def set_tax_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.tax_stone)
    await state.update_data(menu_message_id=call.message.message_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акрил", callback_data="tax_stone_acryl")],
        [InlineKeyboardButton(text="Кварц", callback_data="tax_stone_quartz")],
    ])
    msg = await call.message.answer("Выберите тип камня:", reply_markup=kb)
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def tax_stone_choice(call: CallbackQuery, state: FSMContext):
    stone = "acryl" if call.data.endswith("acryl") else "quartz"
    data = await state.get_data()
    prompt_id = data.get("prompt_id")
    await state.set_state(Settings.tax)
    await state.update_data(stone=stone)
    await safe_edit_message_text(
        call.message.edit_text,
        "Введите процент (целое число от 0 до 100):",
    )
    await call.answer()


async def tax_input(message: Message, state: FSMContext):
    data = await state.get_data()
    menu_id = data.get("menu_message_id")
    prompt_id = data.get("prompt_id")
    stone = data.get("stone")

    text = message.text.strip().rstrip('%')
    if not text.isdigit():
        return await message.reply("Неверный формат. Введите число (например, 15).")

    # 1) Сохраняем процент в БД
    if stone:
        await set_tax_value(message.chat.id, stone, text)
    else:
        await set_tax(message.chat.id, text)

    # 2) Удаляем сообщение пользователя и подсказку
    await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    # 3) Завершаем FSM-состояние
    await state.clear()

    # 4) Редактируем то же сообщение-меню
    tax  = await get_tax(message.chat.id)
    fix = await get_measurement_fix(message.chat.id)
    km  = await get_measurement_km(message.chat.id)
    mop = await get_menu3_mop(message.chat.id)
    margin = await get_menu3_margin(message.chat.id)
    await safe_edit_message_text(message.bot.edit_message_text, 
        text="Параметры:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=main_menu(tax, fix, km, mop, margin)
    )

async def set_measurement_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.meas_menu)
    await state.update_data(menu_message_id=call.message.message_id)
    fix = await get_measurement_fix(call.message.chat.id)
    km  = await get_measurement_km(call.message.chat.id)
    await safe_edit_message_text(call.message.edit_text, "Введите стоимость выезда:", reply_markup=meas_submenu(fix, km))
    await call.answer()

async def meas_fix_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.meas_fix)
    data = await state.get_data()
    await state.update_data(menu_message_id=data["menu_message_id"])
    msg = await call.message.answer("Введите фиксированную стоимость выезда для замеров (₽):")
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def price_inst_deliv_km_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.meas_km)
    data = await state.get_data()
    await state.update_data(menu_message_id=data["menu_message_id"])
    msg = await call.message.answer("Введите стоимость одного километра (₽):")
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def meas_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tax  = await get_tax(call.message.chat.id)
    fix  = await get_measurement_fix(call.message.chat.id)
    km   = await get_measurement_km(call.message.chat.id)
    mop  = await get_menu3_mop(call.message.chat.id)
    margin = await get_menu3_margin(call.message.chat.id)
    await safe_edit_message_text(call.message.edit_text, "Параметры:", reply_markup=main_menu(tax, fix, km, mop, margin))
    await call.answer()

async def meas_fix_input(message: Message, state: FSMContext):
    data    = await state.get_data()
    menu_id = data["menu_message_id"]
    prompt_id = data.get("prompt_id")
    text    = message.text.strip().rstrip('₽')
    if not text.isdigit():
        return await message.reply("Введите число, например: 3000")
    await set_measurement_fix(message.chat.id, text)
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
    await state.set_state(Settings.meas_menu)
    fix = await get_measurement_fix(message.chat.id)
    km  = await get_measurement_km(message.chat.id)
    await safe_edit_message_text(message.bot.edit_message_text, 
        text="Введите стоимость выезда:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=meas_submenu(fix, km)
    )

async def price_inst_deliv_km_input(message: Message, state: FSMContext):
    data    = await state.get_data()
    menu_id = data["menu_message_id"]
    prompt_id = data.get("prompt_id")
    text    = message.text.strip().rstrip('₽')
    if not text.isdigit():
        return await message.reply("Введите число, например: 20")
    await set_measurement_km(message.chat.id, text)
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
    await state.set_state(Settings.meas_menu)
    fix = await get_measurement_fix(message.chat.id)
    km  = await get_measurement_km(message.chat.id)
    await safe_edit_message_text(message.bot.edit_message_text, 
        text="Введите стоимость выезда:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=meas_submenu(fix, km)
    )

async def set_mop_main(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.mop_stone)
    await state.update_data(menu_message_id=call.message.message_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акрил", callback_data="mop_stone_acryl")],
        [InlineKeyboardButton(text="Кварц", callback_data="mop_stone_quartz")],
    ])
    msg = await call.message.answer("Выберите тип камня:", reply_markup=kb)
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def mop_stone_choice(call: CallbackQuery, state: FSMContext):
    stone = "acryl" if call.data.endswith("acryl") else "quartz"
    await state.set_state(Settings.menu3_mop)
    await state.update_data(stone=stone)
    await safe_edit_message_text(
        call.message.edit_text,
        "Введите проценты МОПу (целое число от 0 до 100):",
    )
    await call.answer()

async def set_margin_main(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.margin_stone)
    await state.update_data(menu_message_id=call.message.message_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акрил", callback_data="margin_stone_acryl")],
        [InlineKeyboardButton(text="Кварц", callback_data="margin_stone_quartz")],
    ])
    msg = await call.message.answer("Выберите тип камня:", reply_markup=kb)
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def margin_stone_choice(call: CallbackQuery, state: FSMContext):
    stone = "acryl" if call.data.endswith("acryl") else "quartz"
    await state.set_state(Settings.menu3_margin)
    await state.update_data(stone=stone)
    await safe_edit_message_text(
        call.message.edit_text,
        "Введите маржу в % (целое число от 0 до 100):",
    )
    await call.answer()

async def salary_role_menu(call: CallbackQuery, state: FSMContext):
    # call.data == "salary_master" или "salary_installer"
    role = call.data.split("_")[1]      # -> "master" или "installer"
    await state.set_state(Settings.salary_role)
    await state.update_data(menu_message_id=call.message.message_id, role=role)
    await safe_edit_message_text(call.message.edit_text, 
        "Выберите тип камня:",
        reply_markup=stone_menu_kb(role)
    )
    await call.answer()


async def salary_stone_choice(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role, stone = data["role"], call.data.split("_")[2]
    await state.set_state(Settings.salary_stone)
    await state.update_data(stone=stone)
    if role == "master":
        unit = await get_master_unit(call.message.chat.id)
    else:
        unit = await get_installer_unit(call.message.chat.id)
    # забираем текущие значения
    keys = ["countertop","wall"]
    if role=="master":
        keys += ["boil","sink","glue","edges"]
    else:
        keys += ["delivery","delivery_km","takelage"]
    values = {k: await get_salary(call.message.chat.id, f"master_{stone}_{k}" if role=="master" else f"installer_{stone}_{k}")
              for k in keys}
    await safe_edit_message_text(call.message.edit_text, 
        f"Установки для { 'акрилового' if stone=='acryl' else 'кварцевого' } камня:",
        reply_markup=salary_item_kb(role, stone, unit, values)
    )
    await call.answer()

async def salary_stone_back(call: CallbackQuery, state: FSMContext):
    # Возвращаемся в главное меню
    await state.clear()
    tax  = await get_tax(call.message.chat.id)
    fix  = await get_measurement_fix(call.message.chat.id)
    km   = await get_measurement_km(call.message.chat.id)
    mop  = await get_menu3_mop(call.message.chat.id)
    margin = await get_menu3_margin(call.message.chat.id)
    await safe_edit_message_text(call.message.edit_text, 
        "Параметры:",
        reply_markup=main_menu(tax, fix, km, mop, margin)
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
    if item == "delivery":
        msg = await call.message.answer("Введите фиксированную стоимость доставки (₽):")
        await state.update_data(prompt_id=msg.message_id, substep="fix")
    else:
        unit_hint = 'м/п' if item == 'edges' else ('м2' if item in ['countertop','wall','takelage'] else 'шт.')
        msg = await call.message.answer(
            f"Введите сумму для {label} ({unit_hint}):"
        )
        await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def salary_item_input(message: Message, state: FSMContext):
    data   = await state.get_data()
    menu_id= data["menu_message_id"]
    prompt_id = data.get("prompt_id")
    role, stone, item = data["role"], data["stone"], data["item"]
    text   = message.text.strip()
    if not text.isdigit():
        return await message.reply("Введите число, например: 1500")

    if item == "delivery":
        step = data.get("substep", "fix")
        if step == "fix":
            await set_salary(message.chat.id, f"{role}_{stone}_delivery", text)
            msg = await message.answer("Введите стоимость за километр (₽):")
            await state.update_data(substep="km", prompt_id=msg.message_id)
            await message.delete()
            if prompt_id:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
            return
        else:
            await set_salary(message.chat.id, f"{role}_{stone}_delivery_km", text)
    else:
        await set_salary(
            message.chat.id,
            f"{role}_{stone}_{item}",
            text
        )
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
    # возвращаемся в меню items
    await state.set_state(Settings.salary_stone)
    if role == "master":
        unit = await get_master_unit(message.chat.id)
    else:
        unit = await get_installer_unit(message.chat.id)
    # заново собрать values как в B)
    keys = ["countertop","wall"] + (["boil","sink","glue","edges"] if role=="master" else ["delivery","delivery_km","takelage"])
    values = {k: await get_salary(message.chat.id, f"{role}_{stone}_{k}") for k in keys}
    await safe_edit_message_text(message.bot.edit_message_text, 
        text=f"Установки для { 'акрилового' if stone=='acryl' else 'кварцевого' } камня:",
        chat_id=message.chat.id,
        message_id=menu_id,
        reply_markup=salary_item_kb(role, stone, unit, values)
    )


async def salary_unit_menu(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")  # salary_role_stone_unit
    role, stone = parts[1], parts[2]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="м2", callback_data=f"salary_{role}_{stone}_unit_m2"),
            InlineKeyboardButton(text="м/п", callback_data=f"salary_{role}_{stone}_unit_mp"),
        ]
    ])
    await call.message.answer("Выберите единицу измерения:", reply_markup=kb)
    await call.answer()


async def salary_unit_choice(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")  # salary_role_stone_unit_m2/mp
    if len(parts) < 5:
        # protect against malformed callback data
        await call.answer("Некорректные данные", show_alert=True)
        return
    role, stone, choice_part = parts[1], parts[2], parts[4]
    choice = "м2" if choice_part == "m2" else "м/п"
    chat_id = call.message.chat.id
    if role == "master":
        await set_master_unit(chat_id, choice)
    else:
        await set_installer_unit(chat_id, choice)

    data = await state.get_data()
    menu_id = data["menu_message_id"]
    # восстановим значения
    keys = ["countertop","wall"] + (["boil","sink","glue","edges"] if role=="master" else ["delivery","delivery_km","takelage"])
    values = {k: await get_salary(chat_id, f"{role}_{stone}_{k}") for k in keys}
    unit = choice
    await safe_edit_message_text(call.message.bot.edit_message_text, 
        text=f"Установки для { 'акрилового' if stone=='acryl' else 'кварцевого' } камня:",
        chat_id=chat_id,
        message_id=menu_id,
        reply_markup=salary_item_kb(role, stone, unit, values)
    )
    await call.message.delete()
    await call.answer(f"Выбрано: {choice}")

# ─── 6) Хендлеры для меню 2 ──────────────────────────────────

async def to_menu2(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu2)
    await state.update_data(menu2_message_id=call.message.message_id)

    chat_id = call.message.chat.id
    current_stone  = await get_general_stone_type(chat_id)
    current_price  = await get_stone_price(chat_id)
    unit           = await get_unit(chat_id)
    cntp_m2        = await get_menu2_value(chat_id, "countertop", "м2")
    cntp_mp        = await get_menu2_value(chat_id, "countertop", "м/п")
    cntp           = f"{cntp_m2} м2 | {cntp_mp} п/м"

    wal_m2         = await get_menu2_value(chat_id, "wall", "м2")
    wal_mp         = await get_menu2_value(chat_id, "wall", "м/п")
    wal            = f"{wal_m2} м2 | {wal_mp} п/м"

    bo             = await get_menu2_boil(chat_id)
    si             = await get_menu2_sink(chat_id)
    gl             = await get_menu2_glue(chat_id)
    ed             = await get_menu2_value(chat_id, "edges", "м/п")

    await safe_edit_message_text(call.message.edit_text, 
        "Основное меню 2:",
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
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
    await safe_edit_message_text(call.message.edit_text, 
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

    current_price = await get_stone_price(chat_id)
    unit          = await get_unit(chat_id)
    cntp_m2 = await get_menu2_value(chat_id, "countertop", "м2")
    cntp_mp = await get_menu2_value(chat_id, "countertop", "м/п")
    cntp = f"{cntp_m2} м2 | {cntp_mp} п/м"

    wal_m2 = await get_menu2_value(chat_id, "wall", "м2")
    wal_mp = await get_menu2_value(chat_id, "wall", "м/п")
    wal = f"{wal_m2} м2 | {wal_mp} п/м"

    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_value(chat_id, "edges", "м/п")

    await safe_edit_message_text(call.message.edit_text, 
        "Основное меню 2:",
        reply_markup=menu2_kb(
            selected,           # тип камня
            current_price,
            cntp, wal, bo, si, gl, ed,
            unit
        )
    )
    await state.set_state(Settings.menu2)
    await call.answer(f"Выбрано: {selected}")



async def stone_price_menu(call: CallbackQuery, state: FSMContext):
    # Переключаемся в состояние ввода цены за камень
    await state.set_state(Settings.stone_price)
    data = await state.get_data()
    await state.update_data(menu2_message_id=data["menu2_message_id"])
    msg = await call.message.answer("Введите цену за камень (только цифры):")
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()

async def stone_price_input(message: Message, state: FSMContext):
    data     = await state.get_data()
    menu2_id = data["menu2_message_id"]
    prompt_id = data.get("prompt_id")
    text     = message.text.strip()
    if not text.isdigit():
        return await message.reply("Неверно. Введите число, например: 5000")

    chat_id = message.chat.id
    await set_stone_price(chat_id, text)
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    await state.set_state(Settings.menu2)

    current_stone  = await get_general_stone_type(chat_id)
    current_price  = text
    unit           = await get_unit(chat_id)
    cntp_m2 = await get_menu2_value(chat_id, "countertop", "м2")
    cntp_mp = await get_menu2_value(chat_id, "countertop", "м/п")
    cntp = f"{cntp_m2} м2 | {cntp_mp} п/м"

    wal_m2 = await get_menu2_value(chat_id, "wall", "м2")
    wal_mp = await get_menu2_value(chat_id, "wall", "м/п")
    wal = f"{wal_m2} м2 | {wal_mp} п/м"

    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_value(chat_id, "edges", "м/п")

    await safe_edit_message_text(message.bot.edit_message_text, 
        text="Основное меню 2:",
        chat_id=chat_id,
        message_id=menu2_id,
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            unit
        )
    )



async def back_to_main(call: CallbackQuery, state: FSMContext):
    # Возвращаемся в главное меню
    await state.clear()
    tax  = await get_tax(call.message.chat.id)
    fix  = await get_measurement_fix(call.message.chat.id)
    km   = await get_measurement_km(call.message.chat.id)
    mop  = await get_menu3_mop(call.message.chat.id)
    margin = await get_menu3_margin(call.message.chat.id)
    await safe_edit_message_text(call.message.edit_text, 
        "Привет! Настройте параметры:",
        reply_markup=main_menu(tax, fix, km, mop, margin)
    )
    await call.answer()

# ─── 6.1) Переход в ввод конкретной строки меню 2 ─────────────
async def menu2_item_menu(call: CallbackQuery, state: FSMContext):
    """Показываем выбор единицы для ввода значения."""
    key = call.data  # «menu2_countertop» и т. д.
    await state.update_data(
        menu2_item_key=key,
        menu2_message_id=call.message.message_id,
    )

    label = {
        "menu2_countertop": "Столешница",
        "menu2_wall": "Стеновая",
        "menu2_boil": "Вырез варка",
        "menu2_sink": "Вырез мойка",
        "menu2_glue": "Подклейка",
        "menu2_edges": "Бортики",
    }[key]

    if key == "menu2_countertop":
        await state.set_state(Settings.countertop_menu)
        chat_id = call.message.chat.id
        m2_val = await get_menu2_value(chat_id, "countertop", "м2")
        mp_val = await get_menu2_value(chat_id, "countertop", "м/п")
        await safe_edit_message_text(call.message.edit_text, 
            "Вы нажали \u00abСтолешница\u00bb, введите значение для каждой единицы измерения.",
            reply_markup=countertop_submenu(m2_val, mp_val),
        )
        await call.answer()
        return

    if key == "menu2_wall":
        await state.set_state(Settings.wall_menu)
        chat_id = call.message.chat.id
        m2_val = await get_menu2_value(chat_id, "wall", "м2")
        mp_val = await get_menu2_value(chat_id, "wall", "м/п")
        await safe_edit_message_text(call.message.edit_text, 
            "Вы нажали \u00abСтеновая\u00bb, введите значение для каждой единицы измерения.",
            reply_markup=wall_submenu(m2_val, mp_val),
        )
        await call.answer()
        return
    if key == "menu2_edges":
        await state.set_state(Settings.menu2_item)
        await state.update_data(measure_type="mp")
        msg = await call.message.answer(
            f"Введите значение для {label} (м/п):"
        )
        await state.update_data(prompt_id=msg.message_id)
    else:
        await state.set_state(Settings.menu2_item)
        unit_type = "шт"
        msg = await call.message.answer(f"Введите значение для {label} ({unit_type}):")
        await state.update_data(prompt_id=msg.message_id)
    await call.answer()


async def menu2_unit_choice(call: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор единицы для столешницы/стеновой/бортиков."""
    choice = "m2" if call.data == "menu2_unit_m2" else "mp"
    data = await state.get_data()
    key = data["menu2_item_key"]
    label = {
        "menu2_countertop": "Столешница",
        "menu2_wall": "Стеновая",
        "menu2_edges": "Бортики",
    }[key]

    await state.update_data(measure_type=choice)
    await state.set_state(Settings.menu2_item)
    msg = await call.message.answer(
        f"Введите значение для {label} ({'м2' if choice == 'm2' else 'м/п'}):"
    )
    await state.update_data(prompt_id=msg.message_id)
    await call.message.delete()
    await call.answer()


async def countertop_unit_menu(call: CallbackQuery, state: FSMContext):
    unit = "м2" if call.data == "counter_m2" else "м/п"
    await state.set_state(Settings.countertop_input)
    data = await state.get_data()
    await state.update_data(counter_unit=unit, menu2_message_id=data["menu2_message_id"])
    msg = await call.message.answer(f"Введите значение столешницы для {unit}:")
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()


async def countertop_value_input(message: Message, state: FSMContext):
    data = await state.get_data()
    unit = data.get("counter_unit")
    menu2_id = data.get("menu2_message_id")
    prompt_id = data.get("prompt_id")
    text = message.text.strip()

    parts = text.split(',')
    if len(parts) == 1:
        valid = text.isdigit()
    else:
        valid = len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
    if not valid:
        return await message.reply("Неверный формат. Для дробей используйте запятую, например: 2,3")

    to_store = text.replace(',', '.')
    await set_menu2_value(message.chat.id, "countertop", unit, to_store)

    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    m2_val = await get_menu2_value(message.chat.id, "countertop", "м2")
    mp_val = await get_menu2_value(message.chat.id, "countertop", "м/п")
    await safe_edit_message_text(message.bot.edit_message_text, 
        text="Вы нажали \u00abСтолешница\u00bb, введите значение для каждой единицы измерения.",
        chat_id=message.chat.id,
        message_id=menu2_id,
        reply_markup=countertop_submenu(m2_val, mp_val),
    )
    await state.set_state(Settings.countertop_menu)



async def wall_unit_menu(call: CallbackQuery, state: FSMContext):
    unit = "м2" if call.data == "wall_m2" else "м/п"
    await state.set_state(Settings.wall_input)
    data = await state.get_data()
    await state.update_data(wall_unit=unit, menu2_message_id=data["menu2_message_id"])
    msg = await call.message.answer(f"Введите значение стеновой для {unit}:")
    await state.update_data(prompt_id=msg.message_id)
    await call.answer()


async def wall_value_input(message: Message, state: FSMContext):
    data = await state.get_data()
    unit = data.get("wall_unit")
    menu2_id = data.get("menu2_message_id")
    prompt_id = data.get("prompt_id")
    text = message.text.strip()

    parts = text.split(',')
    if len(parts) == 1:
        valid = text.isdigit()
    else:
        valid = len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
    if not valid:
        return await message.reply("Неверный формат. Для дробей используйте запятую, например: 2,3")

    to_store = text.replace(',', '.')
    await set_menu2_value(message.chat.id, "wall", unit, to_store)

    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    m2_val = await get_menu2_value(message.chat.id, "wall", "м2")
    mp_val = await get_menu2_value(message.chat.id, "wall", "м/п")
    await safe_edit_message_text(message.bot.edit_message_text, 
        text="Вы нажали \u00abСтеновая\u00bb, введите значение для каждой единицы измерения.",
        chat_id=message.chat.id,
        message_id=menu2_id,
        reply_markup=wall_submenu(m2_val, mp_val),
    )
    await state.set_state(Settings.wall_menu)



async def countertop_back(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu2)
    data = await state.get_data()
    menu2_id = data.get("menu2_message_id")
    chat_id = call.message.chat.id

    current_stone = await get_general_stone_type(chat_id)
    current_price = await get_stone_price(chat_id)
    unit = await get_unit(chat_id)
    cntp_m2 = await get_menu2_value(chat_id, "countertop", "м2")
    cntp_mp = await get_menu2_value(chat_id, "countertop", "м/п")
    cntp = f"{cntp_m2} м2 | {cntp_mp} п/м"

    wal_m2 = await get_menu2_value(chat_id, "wall", "м2")
    wal_mp = await get_menu2_value(chat_id, "wall", "м/п")
    wal = f"{wal_m2} м2 | {wal_mp} п/м"
    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_value(chat_id, "edges", "м/п")

    await safe_edit_message_text(call.message.edit_text, 
        "Основное меню 2:",
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            unit,
        ),
    )
    await call.answer()


async def wall_back(call: CallbackQuery, state: FSMContext):
    await state.set_state(Settings.menu2)
    data = await state.get_data()
    menu2_id = data.get("menu2_message_id")
    chat_id = call.message.chat.id

    current_stone = await get_general_stone_type(chat_id)
    current_price = await get_stone_price(chat_id)
    unit = await get_unit(chat_id)
    cntp_m2 = await get_menu2_value(chat_id, "countertop", "м2")
    cntp_mp = await get_menu2_value(chat_id, "countertop", "м/п")
    cntp = f"{cntp_m2} м2 | {cntp_mp} п/м"
    wal_m2 = await get_menu2_value(chat_id, "wall", "м2")
    wal_mp = await get_menu2_value(chat_id, "wall", "м/п")
    wal = f"{wal_m2} м2 | {wal_mp} п/м"

    bo   = await get_menu2_boil(chat_id)
    si   = await get_menu2_sink(chat_id)
    gl   = await get_menu2_glue(chat_id)
    ed   = await get_menu2_value(chat_id, "edges", "м/п")

    await safe_edit_message_text(call.message.edit_text, 
        "Основное меню 2:",
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            unit,
        ),
    )
    await call.answer()

# ─── 6.2) Обработка ввода текста для одной из шести строк ────
async def menu2_item_input(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data["menu2_item_key"]
    menu2_id = data["menu2_message_id"]
    prompt_id = data.get("prompt_id")
    measure_type = data.get("measure_type", "single")
    text = message.text.strip()

    # 1) Определяем, для какого ключа ввод:
    #    - «Столешница», «Стеновая», «Бортики» → разрешаем десятичные через запятую (например, "2,3").
    #      Фактически, эти ключи: "menu2_countertop", "menu2_wall", "menu2_edges".
    #    - Для остальных ("menu2_boil", "menu2_sink", "menu2_glue") → только целые (без запятой).

    if key in {"menu2_countertop", "menu2_wall", "menu2_edges"}:
        # для м2 и м/п разрешаем дробные значения через запятую
        parts = text.split(",")
        if len(parts) == 1:
            valid = text.isdigit()
        else:
            valid = len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
        if not valid:
            return await message.reply(
                "Неверный формат. Для дробей используйте запятую, например: 2,3"
            )
    else:
        if not text.isdigit():
            return await message.reply("Неверный формат. Введите целое число, например: 5")

    # 2) Заменяем запятую на точку перед сохранением (чтобы в БД хранилось "2.3" вместо "2,3")
    to_store = text.replace(",", ".")

    if key in {"menu2_countertop", "menu2_wall", "menu2_edges"}:
        field = key.split("_")[1]  # countertop / wall / edges
        await set_menu2_value(
            message.chat.id,
            field,
            "м2" if measure_type == "m2" else "м/п",
            to_store,
        )
    else:
        # boil / sink / glue
        setter = {
            "menu2_boil": set_menu2_boil,
            "menu2_sink": set_menu2_sink,
            "menu2_glue": set_menu2_glue,
        }[key]
        await setter(message.chat.id, to_store)

    # 4) Удаляем сообщение пользователя и подсказку
    await message.delete()
    if prompt_id:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)

    # 5) Возвращаемся в menu2, подгружая все шесть значений и остальные параметры заново
    await state.set_state(Settings.menu2)
    current_stone = await get_general_stone_type(message.chat.id)
    current_price = await get_stone_price(message.chat.id)
    unit = await get_unit(message.chat.id)
    cntp_m2 = await get_menu2_value(message.chat.id, "countertop", "м2")
    cntp_mp = await get_menu2_value(message.chat.id, "countertop", "м/п")
    cntp = f"{cntp_m2} м2 | {cntp_mp} п/м"

    wal_m2 = await get_menu2_value(message.chat.id, "wall", "м2")
    wal_mp = await get_menu2_value(message.chat.id, "wall", "м/п")
    wal  = f"{wal_m2} м2 | {wal_mp} п/м"

    bo   = await get_menu2_boil(message.chat.id)
    si   = await get_menu2_sink(message.chat.id)
    gl   = await get_menu2_glue(message.chat.id)
    # Для бортиков всегда используем значение в м/п независимо от выбранной
    # единицы измерения меню.
    ed   = await get_menu2_value(message.chat.id, "edges", "м/п")
    await safe_edit_message_text(message.bot.edit_message_text, 
        text="Основное меню 2:",
        chat_id=message.chat.id,
        message_id=menu2_id,
        reply_markup=menu2_kb(
            current_stone, current_price,
            cntp, wal, bo, si, gl, ed,
            unit
        )
    )

async def menu3_takelage_input(call: CallbackQuery, state: FSMContext):
    choice = "да" if call.data == "takel_yes" else "нет"
    chat_id = call.message.chat.id

    # Сохраняем выбор
    await set_menu2_takelage(chat_id, choice)

    # Возвращаем FSM в состояние Settings.menu3
    data = await state.get_data()
    menu3_id = data["menu3_message_id"]
    prompt_id = data.get("prompt_id")
    await state.set_state(Settings.menu3)

    km_current = await get_menu3_km(chat_id)

    # Удаляем сообщение с кнопками
    await call.message.delete()
    if prompt_id and prompt_id != call.message.message_id:
        await call.message.bot.delete_message(chat_id=chat_id, message_id=prompt_id)

    # Перерисовываем меню 3
    await safe_edit_message_text(call.message.bot.edit_message_text, 
        "Логистика:",
        reply_markup=menu3_kb(km_current, choice),
        chat_id=chat_id,
        message_id=menu3_id,
    )
    await call.answer(f"Такелаж: {choice}")


# ─── где-то после всех существующих хендлеров (но до запуска dp.start_polling) ───
# ─── Объединённый хендлер «Рассчитать» ───────────────────────────
async def calculate_handler(call: CallbackQuery, state: FSMContext):
    chat_id = call.message.chat.id
    unit = await get_unit(chat_id)  # "м2" или "м/п"
    master_unit = await get_master_unit(chat_id)
    installer_unit = await get_installer_unit(chat_id)

    # ─── 1) Расчёт стоимости материала ────────────────────────────

    price_str = await get_stone_price(chat_id)       # строка, например "5000" или "не указано"

    def to_float(x: str) -> float:
        return float(x.replace(",", ".")) if x not in ("не указано", "") else 0.0

    price = to_float(price_str)
    material_cost = price

    def fmt_num(v: float) -> str:
        # если целое, без десятичной части; иначе — через запятую с двумя знаками
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{round(v,2):.2f}".replace(".", ",")

    material_log = [
        "📋 Расчёт стоимости материала:\n",
        f"• Цена за камень: {fmt_num(price)} ₽",
        "─────────────────────────",
        f"Итого материал: {fmt_num(material_cost)} ₽",
    ]
    # заменяем текст меню 3 на лог материала
    await safe_edit_message_text(call.message.edit_text, "\n".join(material_log))

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
    raw_val_ctp   = await get_menu2_value(chat_id, "countertop", master_unit)
    raw_val_wall  = await get_menu2_value(chat_id, "wall", master_unit)
    raw_val_boil  = await get_menu2_boil(chat_id)
    raw_val_sink  = await get_menu2_sink(chat_id)
    raw_val_glue  = await get_menu2_glue(chat_id)
    raw_val_edges = await get_menu2_value(chat_id, "edges", "м/п")

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
        f"    цена мастера за {master_unit} = {fmt_price(price_ctp)} ₽, "
        f"площадь = {disp(raw_val_ctp)} {master_unit} → "
        f"{fmt_price(price_ctp)} × {disp(raw_val_ctp)} = {fmt_cost(cost_ctp)} ₽\n",
        f"• Стеновая:\n"
        f"    цена мастера за {master_unit} = {fmt_price(price_wall)} ₽, "
        f"площадь = {disp(raw_val_wall)} {master_unit} → "
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
        f"    цена мастера за м/п = {fmt_price(price_edges)} ₽, "
        f"длина = {disp(raw_val_edges)} м/п → "
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
    raw_inst_deliv_km = await get_salary(chat_id, f"installer_{stone_key}_delivery_km")
    raw_inst_takel = await get_salary(chat_id, f"installer_{stone_key}_takelage")
    raw_km_qty = await get_menu3_km(chat_id)

    price_inst_ctp = to_float_zero(raw_inst_ctp)
    price_inst_wall = to_float_zero(raw_inst_wall)
    price_inst_deliv = to_float_zero(raw_inst_deliv)
    price_inst_deliv_km = to_float_zero(raw_inst_deliv_km)
    price_inst_takel = to_float_zero(raw_inst_takel)
    km_qty = int(raw_km_qty) if raw_km_qty.isdigit() else 0

    # Пользовательские количества в единицах монтажника
    raw_inst_val_ctp = await get_menu2_value(chat_id, "countertop", installer_unit)
    raw_inst_val_wall = await get_menu2_value(chat_id, "wall", installer_unit)

    inst_val_ctp = parse_area(raw_inst_val_ctp)
    inst_val_wall = parse_area(raw_inst_val_wall)

    # Монтажнику нужны только столешница и стеновая
    cost_inst_ctp = price_inst_ctp * inst_val_ctp
    cost_inst_wall = price_inst_wall * inst_val_wall

    # Доставка: фиксированная сумма + стоимость километров
    cost_inst_delivery_km = price_inst_deliv_km * km_qty
    cost_inst_delivery = price_inst_deliv + cost_inst_delivery_km

    # Такелаж: смотрим флаг из БД (menu2_takelage: "да"/"нет")
    raw_takel_flag = await get_menu2_takelage(chat_id)  # "да"/"нет"/"не указано"
    takelage_cost = 0.0
    if raw_takel_flag == "да":
        # если пользователь выбрал «да», тогда считаем:
        # (сумма длин/площадей в единицах монтажника) × цена за такелаж
        takelage_cost = price_inst_takel * (inst_val_ctp + inst_val_wall)

    total_inst = cost_inst_ctp + cost_inst_wall + cost_inst_delivery + takelage_cost

    inst_log = [
        "\n📋 Расчёт ЗП монтажника (тип камня: " + stone_text + "):\n",
        f"• Столешница:\n"
        f"    цена монтажника за {installer_unit} = {fmt_price(price_inst_ctp)} ₽, "
        f"площадь = {disp(raw_inst_val_ctp)} {installer_unit} → "
        f"{fmt_price(price_inst_ctp)} × {disp(raw_inst_val_ctp)} = {fmt_cost(cost_inst_ctp)} ₽\n",
        f"• Стеновая:\n"
        f"    цена монтажника за {installer_unit} = {fmt_price(price_inst_wall)} ₽, "
        f"площадь = {disp(raw_inst_val_wall)} {installer_unit} → "
        f"{fmt_price(price_inst_wall)} × {disp(raw_inst_val_wall)} = {fmt_cost(cost_inst_wall)} ₽\n",
        f"• Доставка:\n"
        f"    фиксированная сумма = {fmt_price(price_inst_deliv)} ₽\n",
        f"    {km_qty} км × {fmt_price(price_inst_deliv_km)} ₽/км = {fmt_cost(cost_inst_delivery_km)} ₽\n",
    ]

    if raw_takel_flag == "да":
        inst_log += [
            f"• Такелаж:\n"
            f"    цена монтажника за {installer_unit} = {fmt_price(price_inst_takel)} ₽, "
            f"суммарная длина = {disp(raw_inst_val_ctp)} + {disp(raw_inst_val_wall)} = {fmt_num(inst_val_ctp + inst_val_wall)} {installer_unit} → "
            f"{fmt_price(price_inst_takel)} × {fmt_num(inst_val_ctp + inst_val_wall)} = {fmt_cost(takelage_cost)} ₽\n"
        ]
    else:
        inst_log += ["• Такелаж: нет → 0 ₽\n"]

    inst_log += [
        "────────────────────────────────\n",
        f"Итого ЗП монтажника: {fmt_cost(total_inst)} ₽"
    ]

    # ─── 4) Расчёт стоимости замеров ────────────────────────────────
    raw_meas_fix = await get_measurement_fix(chat_id)  # строка, напр. "3000" или "не указано"
    raw_meas_km  = await get_measurement_km(chat_id)

    meas_fix = to_float_zero(raw_meas_fix)
    meas_km  = to_float_zero(raw_meas_km)

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

    # читаем проценты с учётом выбранного камня
    raw_margin = await get_margin_value(chat_id, stone_key)
    raw_mop    = await get_mop_value(chat_id, stone_key)
    raw_tax    = await get_tax_value(chat_id, stone_key)


    # преобразуем к float, если не указано — 0
    margin = to_float_zero(raw_margin)
    mop = to_float_zero(raw_mop)
    tax = to_float_zero(raw_tax)

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
    dp.callback_query.register(tax_stone_choice, lambda c: c.data in {"tax_stone_acryl", "tax_stone_quartz"})
    dp.message.register     (tax_input, Settings.tax)

    dp.callback_query.register(set_measurement_menu, lambda c: c.data == "set_measurement_cost")
    dp.callback_query.register(meas_fix_menu, lambda c: c.data == "meas_fix")
    dp.callback_query.register(price_inst_deliv_km_menu, lambda c: c.data == "price_inst_deliv_km")
    dp.callback_query.register(meas_back, lambda c: c.data == "meas_back")
    dp.message.register(meas_fix_input, Settings.meas_fix)
    dp.message.register(price_inst_deliv_km_input, Settings.meas_km)
    dp.callback_query.register(set_mop_main, lambda c: c.data == "set_mop")
    dp.callback_query.register(mop_stone_choice, lambda c: c.data in {"mop_stone_acryl", "mop_stone_quartz"})
    dp.callback_query.register(set_margin_main, lambda c: c.data == "set_margin")
    dp.callback_query.register(margin_stone_choice, lambda c: c.data in {"margin_stone_acryl", "margin_stone_quartz"})
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
    dp.callback_query.register(
        salary_unit_menu,
        lambda c: c.data.startswith("salary_") and c.data.endswith("_unit")
    )
    dp.callback_query.register(
        salary_unit_choice,
        lambda c: (
            c.data.startswith("salary_")
            and (c.data.endswith("_unit_m2") or c.data.endswith("_unit_mp"))
        )
    )
    dp.message.register     (salary_item_input,     Settings.salary_item)
    # ─── Регистрация для меню 2 ─────────────────────────────
    dp.callback_query.register(to_menu2, lambda c: c.data == "to_menu2")
    dp.callback_query.register(first_stone_choice, lambda c: c.data == "set_first_stone")
    dp.callback_query.register(stone2_selected, lambda c: c.data in ("stone2_acryl", "stone2_quartz"))
    dp.callback_query.register(stone_price_menu, lambda c: c.data == "set_stone_price")
    dp.message.register(stone_price_input, Settings.stone_price)
    dp.callback_query.register(back_to_main, lambda c: c.data == "back_to_main")
    # ─── регистрируем шесть новых пунктов menu2 ──────────────
    dp.callback_query.register(menu2_item_menu, lambda c: c.data in {"menu2_countertop", "menu2_wall", "menu2_boil", "menu2_sink", "menu2_glue", "menu2_edges"})
    dp.callback_query.register(menu2_unit_choice, lambda c: c.data in {"menu2_unit_m2", "menu2_unit_mp"})
    dp.callback_query.register(countertop_unit_menu, lambda c: c.data in {"counter_m2", "counter_mp"})
    dp.callback_query.register(countertop_back, lambda c: c.data == "counter_back")
    dp.message.register(countertop_value_input, Settings.countertop_input)

    dp.callback_query.register(wall_unit_menu, lambda c: c.data in {"wall_m2", "wall_mp"})
    dp.callback_query.register(wall_back, lambda c: c.data == "wall_back")
    dp.message.register(wall_value_input, Settings.wall_input)

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
    dp.callback_query.register(menu3_takelage_menu, lambda c: c.data == "menu3_takelage")
    dp.callback_query.register(menu3_takelage_input, lambda c: c.data in {"takel_yes", "takel_no"})

    # ─── (где-то после всех определений menu3_* и перед dp.start_polling) ─────────────────────────────────────

    # Регистрируем кнопку «Рассчитать»
    # dp.callback_query.register(calculate_master_salary, lambda c: c.data == "calculate")

    # ─── (далее идёт await dp.start_polling(bot)) ──────────────────────────────────────────────────────────

    # ─── после этой строки идёт await dp.start_polling(bot) ───

    # Запускаем long-polling
    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
