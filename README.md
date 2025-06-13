# Calculator Bot

A Telegram bot that helps calculate the cost of stone products and salaries of workers. Users configure parameters such as units, tax percentage and wages and then receive a full calculation via the `Рассчитать` button.

## Requirements
- **Python** 3.11 or newer
- **aiogram** (Telegram framework)
- **aiosqlite** (async SQLite driver)

All dependencies in requirements.txt have their versions pinned to ensure consistent installations.

Install them with:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Database
The bot stores user settings in `settings.db`. The database is created and initialized automatically on the first start. No manual actions are required.

## Running the bot
1. Place your bot token into `main.py` (``API_TOKEN`` variable).
2. Start the bot:

```bash
python main.py
```
The dispatcher uses long polling. The code sets `polling_timeout=1` so the bot
responds quickly even after periods of inactivity. Adjust this value if you
need a different balance between latency and network traffic.

## Main commands
- `/start` — reset the state and open the main menu.
- `/settings` — same as tapping "Настройки" on the home screen.
- "Единица измерения" — choose units (m² or linear meters).
- "Система налогов" — configure tax percentages separately for quartz and acrylic.
- "Стоимость замеров" — configure fixed price and per‑kilometer price for measurements.
- "МОП" — set overhead percentage separately for quartz and acrylic.
- "Маржа" — set profit margin separately for quartz and acrylic.
- "ЗП Мастера" / "ЗП Монтажника" — set wages for each role. Installer delivery now has fixed and per‑kilometer components, editable from this menu.
- "Далее" opens extra menus to provide dimensions, material prices and other values.
- "Рассчитать" — receive a detailed breakdown of material cost and salaries.

The bot uses inline keyboards for navigation. After adjusting all parameters, press "Рассчитать" to see the final calculation. Taxes, overhead (МОП) and margin are stored separately for quartz and acrylic, and the calculation applies the values for the stone selected in menu 2.


## License

This project is licensed under the [MIT License](LICENSE).
