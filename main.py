import io
import os
import json
import logging
from datetime import datetime

import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ta.trend import EMAIndicator

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"

HISTORY_FILE = "signal_history.json"

PAIRS = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "USDJPY=X",
    "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    "NZD/USD": "NZDUSD=X",
}

TIMEFRAMES = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m"
}

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def calculate_signal(df):
    if df is None or df.empty:
        return "Немає даних", "🟡"

    close = df["Close"]
    rsi = RSIIndicator(close, window=14).rsi()
    ema = EMAIndicator(close, window=21).ema_indicator()
    bb = BollingerBands(close, window=20, window_dev=2)
    bb_high = bb.bollinger_hband()
    bb_low = bb.bollinger_lband()

    last_close = close.iloc[-1]
    last_rsi = rsi.iloc[-1]
    last_ema = ema.iloc[-1]
    last_bb_high = bb_high.iloc[-1]
    last_bb_low = bb_low.iloc[-1]

    # Логіка сигналів
    if last_rsi < 30 and last_close < last_bb_low and last_close > last_ema:
        return "Купувати", "🟢"
    elif last_rsi > 70 and last_close > last_bb_high and last_close < last_ema:
        return "Продавати", "🔴"
    else:
        return "Тримати", "🟡"

def generate_chart(df, pair_name):
    plt.style.use('seaborn-darkgrid')
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(df.index, df['Close'], label='Close')
    ax.plot(df.index, EMAIndicator(df['Close'], 21).ema_indicator(), label='EMA 21')

    bb = BollingerBands(df['Close'], 20, 2)
    ax.plot(df.index, bb.bollinger_hband(), label='BB High', linestyle='--', color='gray')
    ax.plot(df.index, bb.bollinger_lband(), label='BB Low', linestyle='--', color='gray')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.set_title(f'Графік {pair_name}')
    ax.legend()
    ax.set_xlabel('Час')
    ax.set_ylabel('Ціна')

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

def pairs_keyboard():
    keyboard = []
    row = []
    for i, pair in enumerate(PAIRS.keys()):
        row.append(InlineKeyboardButton(pair, callback_data=f"pair|{pair}"))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def timeframes_keyboard():
    keyboard = [
        [InlineKeyboardButton(tf, callback_data=f"timeframe|{tf}") for tf in TIMEFRAMES.keys()]
    ]
    return InlineKeyboardMarkup(keyboard)

user_selection = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Вибери валютну пару для отримання сигналу:",
        reply_markup=pairs_keyboard()
    )

async def pair_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair_name = query.data.split("|")[1]

    user_id = query.from_user.id
    user_selection[user_id] = {"pair": pair_name}

    await query.edit_message_text(
        text=f"Обрана пара: {pair_name}\nВибери таймфрейм:",
        reply_markup=timeframes_keyboard()
    )

async def timeframe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    timeframe = query.data.split("|")[1]
    user_id = query.from_user.id

    if user_id not in user_selection or "pair" not in user_selection[user_id]:
        await query.edit_message_text("Спершу обери валютну пару командою /start")
        return

    pair_name = user_selection[user_id]["pair"]
    ticker = PAIRS[pair_name]

    await query.edit_message_text(f"Завантажую дані для {pair_name} з таймфреймом {timeframe}...")

    try:
        df = yf.download(ticker, period="1d", interval=timeframe)
    except Exception as e:
        await query.edit_message_text(f"Помилка завантаження даних: {e}")
        return

    if df.empty:
        await query.edit_message_text("Немає даних для обраної пари та таймфрейму.")
        return

    signal_text, emoji = calculate_signal(df)

    history = load_history()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "pair": pair_name,
        "timeframe": timeframe,
        "signal": signal_text,
    }
    history.setdefault(str(user_id), []).append(entry)
    save_history(history)

    chart = generate_chart(df, pair_name)

    await context.bot.send_photo(
        chat_id=user_id,
        photo=chart,
        caption=f"Сигнал для {pair_name} ({timeframe}): {emoji} {signal_text}"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    history = load_history()

    user_history = history.get(str(user_id), [])
    if not user_history:
        await update.message.reply_text("Історія сигналів порожня.")
        return

    total = len(user_history)
    buy_count = sum(1 for e in user_history if e["signal"] == "Купувати")
    sell_count = sum(1 for e in user_history if e["signal"] == "Продавати")
    hold_count = total - buy_count - sell_count

    msg = (
        f"Статистика сигналів:\n"
        f"Всього: {total}\n"
        f"Купувати: {buy_count}\n"
        f"Продавати: {sell_count}\n"
        f"Тримати: {hold_count}\n"
    )
    await update.message.reply_text(msg)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(pair_handler, pattern=r"^pair\|"))
    app.add_handler(CallbackQueryHandler(timeframe_handler, pattern=r"^timeframe\|"))

    print("Бот запущено")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
