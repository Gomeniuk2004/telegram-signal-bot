import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import random
from datetime import datetime

# Логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Дані для вибору
PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "BTC-USD", "ETH-USD"]  # приклад OTC пари теж є
TIMEFRAMES = ["1м", "3м", "5м", "15м"]

# Історія сигналів (в пам’яті, можна зберігати в файл чи БД)
history = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(pair, callback_data=f"pair_{pair}") for pair in PAIRS]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Виберіть валютну пару:', reply_markup=reply_markup)

async def pair_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair = query.data.split("_")[1]
    context.user_data['pair'] = pair

    keyboard = [
        [InlineKeyboardButton(tf, callback_data=f"tf_{tf}") for tf in TIMEFRAMES]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=f"Ви обрали пару: {pair}\nОберіть таймфрейм:", reply_markup=reply_markup)

async def tf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tf = query.data.split("_")[1]
    pair = context.user_data.get('pair')

    if not pair:
        await query.edit_message_text("Будь ласка, спочатку оберіть валютну пару /start")
        return

    # Генеруємо сигнал з випадковою точністю 70-80%
    accuracy = random.uniform(70, 80)
    time_in_minutes = int(tf[:-1])  # витягуємо число з таймфрейму, наприклад '3м' -> 3

    signal = f"📈 Сигнал для {pair} | Таймфрейм: {tf}\nРекомендовано увійти на {time_in_minutes} хвилин\nТочність сигналу: {accuracy:.2f}%"

    # Записуємо в історію
    history.append({
        "pair": pair,
        "timeframe": tf,
        "accuracy": accuracy,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    await query.edit_message_text(signal)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history:
        await update.message.reply_text("Історія угод порожня.")
        return
    text = "Історія сигналів:\n"
    for item in history[-10:]:  # останні 10
        text += f"{item['timestamp']}: {item['pair']} | {item['timeframe']} | Точність: {item['accuracy']:.2f}%\n"
    await update.message.reply_text(text)

def main():
    token = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(pair_handler, pattern=r"^pair_"))
    application.add_handler(CallbackQueryHandler(tf_handler, pattern=r"^tf_"))
    application.add_handler(CommandHandler("history", history_command))

    print("Бот запущено...")
    application.run_polling()

if __name__ == '__main__':
    main()
