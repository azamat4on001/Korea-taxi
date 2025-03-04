import logging
from telegram import *
from telegram.ext import *
from config import *
from database import *
import haversine as hs
from datetime import datetime
import json

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Загрузка локализаций
def load_locale(lang: str) -> dict:
    with open(f'locales/{lang}.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Состояния
(
    LANG, ROLE, PHONE, CAR_BRAND, CAR_MODEL, CAR_YEAR,
    ORDER_LOCATION, ORDER_DESTINATION, ORDER_SEATS,
    ORDER_TIME, ORDER_URGENT, WAIT_PAYMENT,
    MANUAL_CITY, MANUAL_BRAND
) = range(14)

# --------------- Обработчики ---------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать! Выберите язык:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇷🇺 Русский", callback_data='ru'),
            [InlineKeyboardButton("🇹🇯 Тоҷикӣ", callback_data='tj'),
            [InlineKeyboardButton("🇺🇿 O'zbek", callback_data='uz')]
        ])
    )
    return LANG

async def handle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = query.data
    context.user_data['lang'] = lang
    User.create(user_id=query.from_user.id, language=lang).save()
    locale = load_locale(lang)
    await query.edit_message_text(
        locale['choose_role'],
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(locale['driver'], callback_data='driver'),
            [InlineKeyboardButton(locale['passenger'], callback_data='passenger')]
        ])
    )
    return ROLE

async def handle_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    role = query.data
    context.user_data['role'] = role
    locale = load_locale(context.user_data['lang'])

    if role == 'driver':
        user, created = User.get_or_create(
            user_id=query.from_user.id,
            defaults={'role': 'driver', 'is_approved': False}
        )
        if not user.is_approved:
            payment_text = locale['driver_payment_info'].replace("{PAYMENT_DETAILS}", PAYMENT_DETAILS).replace("{ADMIN_CONTACTS}", ADMIN_CONTACTS)
            await query.message.reply_text(
                payment_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Я оплатил", callback_data='paid')],
                    [InlineKeyboardButton("❌ Отмена", callback_data='cancel')]
                ])
            )
            return WAIT_PAYMENT
    await query.message.reply_text(
        locale['phone_request'],
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📞 Поделиться номером", request_contact=True)]],
            resize_keyboard=True
        )
    )
    return PHONE

async def handle_payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == 'paid':
        locale = load_locale(context.user_data['lang'])
        await context.bot.send_message(
            ADMIN_ID,
            f"⚠️ Новый водитель ожидает подтверждения:\nID: {query.from_user.id}\nUsername: @{query.from_user.username}"
        )
        await query.message.reply_text(locale['payment_received'])
    return ConversationHandler.END

# ... (остальные обработчики: handle_phone, handle_car_brand, handle_location и т.д.)

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANG: [CallbackQueryHandler(handle_lang)],
            ROLE: [CallbackQueryHandler(handle_role)],
            WAIT_PAYMENT: [CallbackQueryHandler(handle_payment_confirmation)],
            PHONE: [MessageHandler(filters.CONTACT, handle_phone)],
            # ... остальные состояния
        },
        fallbacks=[]
    )
    
    application.add_handler(conv_handler)
    application.run_polling()r=user,
        brand=context.user_data['car_brand'],
        model=context.user_data['car_model'],
        year=int(update.message.text)
    )
    await update.message.reply_text("✅ Авто добавлено!")
    return ConversationHandler.END

async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📍 Отправьте ваше местоположение:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Отправить геопозицию", request_location=True)]],
            resize_keyboard=True
        )
    )
    return ORDER_LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    context.user_data['departure_lat'] = location.latitude
    context.user_data['departure_lon'] = location.longitude
    await update.message.reply_text("🏁 Введите город назначения:")
    return ORDER_DESTINATION

async def handle_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    destination = update.message.text
    if destination not in SUPPORTED_CITIES:
        await update.message.reply_text("❌ Город не поддерживается. Введите снова:")
        return ORDER_DESTINATION
    context.user_data['destination'] = destination
    await update.message.reply_text("👥 Сколько мест нужно? (1-4):")
    return ORDER_SEATS

async def handle_seats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seats = int(update.message.text)
    if not 1 <= seats <= 4:
        await update.message.reply_text("❌ Введите число от 1 до 4:")
        return ORDER_SEATS
    context.user_data['seats'] = seats
    
    buttons = [[InlineKeyboardButton(brand, callback_data=f"pref_{brand}")] for brand in BRANDS]
    buttons.append([InlineKeyboardButton("🚕 Без предпочтений", callback_data="pref_none")])
    await update.message.reply_text(
        "🚗 Выберите предпочтительную марку авто:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ORDER_BRAND

async def handle_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    brand = query.data.split('_')[1]
    context.user_data['preferred_brand'] = None if brand == "none" else brand
    
    # Создание заказа
    order = Order.create(
        creator=User.get(User.user_id == query.from_user.id),
        departure_lat=context.user_data['departure_lat'],
        departure_lon=context.user_data['departure_lon'],
        destination=context.user_data['destination'],
        seats=context.user_data['seats'],
        preferred_brand=context.user_data['preferred_brand']
    )
    
    # Публикация в канал
    text = (
        f"🚖 Новый заказ!\n"
        f"📍 Откуда: {context.user_data['departure_lat']}, {context.user_data['departure_lon']}\n"
        f"🏁 Куда: {order.destination}\n"
        f"💺 Мест: {order.seats}\n"
        f"🚗 Марка: {order.preferred_brand or 'Любая'}"
    )
    message = await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Принять заказ", callback_data=f"accept_{order.id}")]
        ])
    )
    order.channel_message_id = message.message_id
    order.save()
    await query.message.reply_text("✅ Заказ опубликован!")
    return ConversationHandler.END

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANG: [CallbackQueryHandler(handle_lang)],
            ROLE: [CallbackQueryHandler(handle_role)],
            PHONE: [MessageHandler(filters.CONTACT, handle_phone)],
            CAR_BRAND: [CallbackQueryHandler(handle_car_brand)],
            CAR_MODEL: [MessageHandler(filters.TEXT, handle_car_model)],
            CAR_YEAR: [MessageHandler(filters.TEXT, handle_car_year)],
            ORDER_LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
            ORDER_DESTINATION: [MessageHandler(filters.TEXT, handle_destination)],
            ORDER_SEATS: [MessageHandler(filters.TEXT, handle_seats)],
            ORDER_BRAND: [CallbackQueryHandler(handle_brand)]
        },
        fallbacks=[]
    )
    
    application.add_handler(conv_handler)
    application.run_polling()