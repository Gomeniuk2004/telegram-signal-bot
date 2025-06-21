import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import yfinance as yf
import pandas as pd
import ta

# Отримуємо токен з Environment Variable
TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

PAIRS = ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'BTC-USD']
TIMEFRAMES = {'1Хв': '1m', '3Хв': '3m', '5Хв': '5m'}

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = ReplyKeyboardMarkup([[p] for p in PAIRS], one_time_keyboard=True)
    await update.message.reply_text("Оберіть валютну пару:", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text in PAIRS:
        user_data[update.effective_user.id] = {'pair': text}
        reply_markup = ReplyKeyboardMarkup([[k] for k in TIMEFRAMES.keys()], one_time_keyboard=True)
        await update.message.reply_text("Оберіть таймфрейм:", reply_markup=reply_markup)
    elif text in TIMEFRAMES:
        pair = user_data.get(update.effective_user.id, {}).get('pair')
        if not pair:
            await update.message.reply_text("Спочатку оберіть валютну пару командою /start")
            return
        tf = TIMEFRAMES[text]
        signal = get_signal(pair, tf)
        result = f"📈 Сигнал для {pair} | Таймфрейм: {text}\n\n{signal}"
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("Будь ласка, оберіть валютну пару або таймфрейм з меню.")

def get_signal(pair, tf):
    try:
        df = yf.download(pair, period='1d', interval=tf)
        df.dropna(inplace=True)
        df['rsi'] = ta.momentum.RSIIndicator(df['Close']).rsi()
        df['ema_fast'] = ta.trend.EMAIndicator(df['Close'], window=5).ema_indicator()
        df['ema_slow'] = ta.trend.EMAIndicator(df['Close'], window=14).ema_indicator()

        latest = df.iloc[-1]
        if latest['rsi'] < 30 and latest['ema_fast'] > latest['ema_slow']:
            return "🟢 Купити (UP)"
        elif latest['rsi'] > 70 and latest['ema_fast'] < latest['ema_slow']:
            return "🔴 Продати (DOWN)"
        else:
            return "⚪️ Нейтральний сигнал"
    except Exception as e:
        return f"⚠️ Помилка: {e}"

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
