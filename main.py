
import yfinance as yf
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime

TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"

user_settings = {}
history = []

def fetch_data(pair: str, interval: str = "1m", limit: int = 100):
    symbol = pair.replace('/', '')
    try:
        data = yf.download(symbol, period="1d", interval=interval)
        return data.tail(limit)
    except Exception as e:
        print(f"Помилка завантаження даних: {e}")
        return None

def generate_signal(df):
    if df is None or df.empty or 'Close' not in df.columns:
        return "⚠️ Дані відсутні або некоректні"

    close = df['Close']
    rsi = RSIIndicator(close, window=14).rsi()
    ema = EMAIndicator(close, window=20).ema_indicator()
    bb = BollingerBands(close)
    upper = bb.bollinger_hband()
    lower = bb.bollinger_lband()

    last_close = close.iloc[-1]
    last_rsi = rsi.iloc[-1]
    last_ema = ema.iloc[-1]
    last_upper = upper.iloc[-1]
    last_lower = lower.iloc[-1]

    if last_rsi < 30 and last_close > last_ema and last_close > last_lower:
        return "⬆️ Buy (вгору на 2 хв)"
    elif last_rsi > 70 and last_close < last_ema and last_close < last_upper:
        return "⬇️ Sell (вниз на 2 хв)"
    return "⏸ Немає чіткого сигналу"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("EUR/USD", callback_data='pair_EUR/USD')],
        [InlineKeyboardButton("GBP/USD", callback_data='pair_GBP/USD')],
        [InlineKeyboardButton("OTC EUR/USD", callback_data='pair_OTC EUR/USD')],
        [InlineKeyboardButton("1 хв", callback_data='tf_1')],
        [InlineKeyboardButton("3 хв", callback_data='tf_3')],
        [InlineKeyboardButton("5 хв", callback_data='tf_5')],
        [InlineKeyboardButton("📈 Отримати сигнал", callback_data='signal')],
        [InlineKeyboardButton("📜 Історія", callback_data='history')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📊 Виберіть валютну пару та таймфрейм:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_settings:
        user_settings[user_id] = {'pair': 'EUR/USD', 'tf': '1m'}

    data = query.data
    if data.startswith("pair_"):
        user_settings[user_id]['pair'] = data[5:]
        await query.edit_message_text(f"✅ Обрана пара: {data[5:]}")
    elif data.startswith("tf_"):
        tf_map = {'1': '1m', '3': '3m', '5': '5m'}
        user_settings[user_id]['tf'] = tf_map[data[3:]]
        await query.edit_message_text(f"✅ Обраний таймфрейм: {data[3:]} хв")
    elif data == "signal":
        pair = user_settings[user_id]['pair']
        tf = user_settings[user_id]['tf']
        df = fetch_data(pair, interval=tf)
        signal = generate_signal(df)
        result = f"📈 Сигнал для {pair} | TF: {tf}
Результат: {signal}"
        history.append({
            'user_id': user_id,
            'pair': pair,
            'tf': tf,
            'signal': signal,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        await query.edit_message_text(result)
    elif data == "history":
        logs = [f"{h['time']} | {h['pair']} | {h['signal']}" for h in history[-5:] if h['user_id'] == user_id]
        await query.edit_message_text("📜 Останні сигнали:
" + "\n".join(logs) if logs else "Історія порожня.")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.run_polling()
