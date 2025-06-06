# Calculator Bot

A Telegram bot that helps calculate the cost of stone products and salaries of workers. Users configure parameters such as units, tax percentage and wages and then receive a full calculation via the `Рассчитать` button.

## Requirements
- **Python** 3.11 or newer
- **aiogram** (Telegram framework)
- **aiosqlite** (async SQLite driver)

Install them with:

```bash
python -m pip install --upgrade pip
pip install aiogram aiosqlite
```

## Database
The bot stores user settings in `settings.db`. The database is created and initialized automatically on the first start. No manual actions are required.

## Running the bot
1. Place your bot token into `main.py` (``API_TOKEN`` variable).
2. Start the bot:

```bash
python main.py
```

## Main commands
- `/start` — reset the state and open the main menu.
- "Единица измерения" — choose units (m² or linear meters).
- "Система налогов" — input your tax percentage.
- "Стоимость замеров" — configure fixed price and per‑kilometer price for measurements.
- "ЗП Мастера" / "ЗП Монтажника" — set wages for each role.
- "Далее" opens extra menus to provide dimensions, material prices and other values.
- "Рассчитать" — receive a detailed breakdown of material cost and salaries.

The bot uses inline keyboards for navigation. After adjusting all parameters, press "Рассчитать" to see the final calculation.


## License

This project is licensed under the [MIT License](LICENSE).
