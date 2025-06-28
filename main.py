# Стандартные библиотеки Python
import requests
import random
import logging
import os
import threading
import socket
from datetime import datetime, time, timedelta
import time as std_time
import pytz

from answers import handle_direct_mention, handle_admin_commands

# Веб-фреймворк
from flask import Flask, jsonify

# База данных
from supabase import create_client

# Telegram Bot API
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove,
                      ChatMemberUpdated, Chat, User, Message)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters, ConversationHandler,
                          CallbackQueryHandler, ChatMemberHandler, JobQueue)

# ===== НАСТРОЙКА ЛОГГИРОВАНИЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Создаем отдельный обработчик для файла
file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Применяем обработчики к корневому логгеру
logger = logging.getLogger()
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())  # Для вывода в консоль

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ['BOT_TOKEN']
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']

# Константы (оставлены без изменений)
CHAT_ID = -1002773219368
ADMIN_USERNAME = "@coffeefin"
ADMIN_ID = 1318872684
SECRET_WORD = "Слово"  # Кодовое слово из правил
GROUP_LINK = "https://t.me/+2angY5dZi2YyZjY6"
TIKTOK_URL = "https://www.tiktok.com/@ваш_аккаунт"
RULES_TEXT = "📜 **Отец терпеть не может нарушителей.**\nКоротко: не спамьте, не спорьте, не умничайте.\nА ещё — найди кодовое слово. Оно понадобится... очень скоро.\n\nПодробности: telegra.ph/Pravila-06-28-2"
REGIME_TEXT = "⏰ **Режим приема заявок:**\n◈ ПН-СБ — 06:00-19:00 (МСК)\n◈ ВС — 08:00-19:00 (МСК)\n\nСистема автоматически отклоняет заявки вне этого окна. Даже не пытайся обойти — я слежу."
HELP_TEXT = """
🆘 <b>Помощь:</b>
▪️ Проблемы с ботом → @coffeefin
▪️ Недоразумения → @coffeefin
▪️ Вопросы без ответов → @coffeefin
▪️ Жалобы → кнопка неактивна

ℹ️ <b>Основные команды:</b>
/start — Главное меню
/help — Эта справка
/cancel_booking — Отменить бронь роли
"""

# Эмодзи для статусов
STATUS_EMOJI = {"Свободен": "🟢", "Бронь": "🟡", "Занята": "🔴"}

# ===== СОСТОЯНИЯ ДЛЯ ConversationHandler =====
(SELECTING_REGION, SELECTING_CHARACTER, ENTERING_SECRET_WORD, ADMIN_PANEL,
 SWAP_ROLES_FIRST, SWAP_ROLES_SECOND, FORCE_CHANGE_ROLE_SELECT,
 FORCE_CHANGE_ROLE_STATUS, CONFIRM_UNBOOK, ADD_ROLE_NAME, ADD_ROLE_REGION, 
 ADD_ROLE_CONFIRM, DELETE_ROLE_SELECT, CONFIRM_DELETE_ROLE) = range(14)

# Инициализация Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== ВЕБ-СЕРВЕР =====
app = Flask(__name__)


@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot_name": "Telegram Bot",
        "message": "Бот работает нормально!"
    })


@app.route('/health')
def health():
    return jsonify({"status": "healthy"})


@app.route('/stats')
def stats():
    try:
        roles = execute_supabase_query(
            supabase.table("roles").select("status"))
        if roles:
            stats = {
                "total_roles": len(roles),
                "free": len([r for r in roles if r["status"] == "Свободен"]),
                "reserved": len([r for r in roles if r["status"] == "Бронь"]),
                "taken": len([r for r in roles if r["status"] == "Занята"])
            }
        else:
            stats = {"error": "Не удалось получить данные о ролях"}
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)})


# Веб-сервер
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"🟠 Порт {port} занят, пробуем порт 8080")
            app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
            print(f"Flask доступен по адресу: http://localhost:{port}")


# ===== УТИЛИТЫ =====
def execute_supabase_query(query):
    """Безопасное выполнение запросов к Supabase"""
    try:
        response = query.execute()
        return response.data if hasattr(response, 'data') else None
    except Exception as e:
        logger.error(f"Supabase error: {e}")
        return None


# ===== КЛАВИАТУРЫ =====
def main_menu():
    return ReplyKeyboardMarkup(
        [["⋄┋ⲬⲞⳠⲨ ⲂⲤⲦⲨⲠⳘⲦЬ┋⋄"], ["⋄┋ⲡⲣⲁⲃυⲗⲁ┋⋄", "⋄┋ⲣⲟⲗυ┋⋄"],
         ["⋄┋ⲣⲉⲯυⲙ ⲡⲣυⲉⲙⲁ ⳅⲁяⲃⲟⲕ┋⋄"], ["⋄┋ⲡⲟⲙⲟⳃь┋⋄", "⋄┋ⲏⲁⲱ ⲦⲓⲕⲦⲟⲕ┋⋄"]],
        resize_keyboard=True)


def regions_keyboard():
    return ReplyKeyboardMarkup(
        [["Мондштадт", "Ли Юэ"], ["Инадзума", "Сумеру"], ["Фонтейн", "Натлан"],
         ["Снежная", "Другие"], ["🔙 Назад в меню"]],
        resize_keyboard=True)


def characters_keyboard(region: str):
    try:
        roles = execute_supabase_query(
            supabase.table("roles").select("*").eq("region", region))
        keyboard = []
        for i in range(0, len(roles), 2):
            row = [roles[i]["name"]]
            if i + 1 < len(roles):
                row.append(roles[i + 1]["name"])
            keyboard.append(row)
        keyboard.append(["🔙 К регионам"])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    except Exception as e:
        logger.error(f"Ошибка получения ролей: {e}")
        return regions_keyboard()


def admin_inline_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔀 Поменять ролями", callback_data="admin_swap"),
            InlineKeyboardButton("🔄 Изменить статус", callback_data="admin_change_status")
        ],
        [
            InlineKeyboardButton("🔓 Освободить роль", callback_data="admin_free"),
            InlineKeyboardButton("➕ Добавить роль", callback_data="admin_add_role")
        ],
        [
            InlineKeyboardButton("🗑 Удалить роль", callback_data="admin_delete_role"),
            InlineKeyboardButton("📋 Текущие роли", callback_data="admin_current")
        ]
    ])


def status_inline_keyboard():
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🟢 Свободен", callback_data="status_free"),
            InlineKeyboardButton("🟡 Бронь", callback_data="status_reserved")
        ],
         [
             InlineKeyboardButton("🔴 Занята", callback_data="status_taken"),
             InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")
         ]])


# ===== ОСНОВНЫЕ КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        user = update.effective_user
        await update.message.reply_text(
            f"*Добро пожаловать, {user.mention_html()}.*\n\n"
            "Я — Клиф, администратор флуда «название_флуда». "
            "Моя задача — провести тебя в священные залы нашего чата.\n\n"
            "📜 *Сначала изучи:*\n"
            "1. Правила (отец терпеть не может нарушителей)\n"
            "2. Список ролей\n"
            "3. График приёма (мы тоже любим поспать)\n\n"
            "Когда изучишь материалы — жми *«Хочу вступить»* и следуй инструкциям.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu())
    return ConversationHandler.END


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def show_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📱 Тыкни сюда", url=TIKTOK_URL)]])
    await update.message.reply_text(
        "Тыкнешь на кнопку — перейдешь в наш тт. Не благодари.",
        reply_markup=keyboard)


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(RULES_TEXT, parse_mode=ParseMode.MARKDOWN)


async def show_regime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(REGIME_TEXT, parse_mode=ParseMode.MARKDOWN)


async def show_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        roles = execute_supabase_query(supabase.table("roles").select("*"))

        text = "📋 *Текущий статус ролей:*\n\n"
        text += f"{STATUS_EMOJI['Свободен']} *Свободен* — бери, пока не заняли\n"
        text += f"{STATUS_EMOJI['Бронь']} *Бронь* — кто-то уже нервно кусает ногти\n"
        text += f"{STATUS_EMOJI['Занята']} *Занята* — даже не пытайся\n\n"

        regions_order = [
            "Мондштадт", "Ли Юэ", "Инадзума", "Сумеру", "Фонтейн", "Натлан",
            "Снежная", "Другие"
        ]

        for region in regions_order:
            region_roles = sorted([r for r in roles if r["region"] == region],
                                  key=lambda x: x["name"])
            if region_roles:
                text += f"\n*=== {region} ===*\n"
                for role in region_roles:
                    emoji = STATUS_EMOJI.get(role["status"], "⚪")
                    text += f"{emoji} {role['name']}\n"

        if len(text) > 3000:
            part1 = text[:3000].rsplit('\n', 1)[0]
            part2 = text[len(part1):]
            await update.message.reply_text(part1,
                                            parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text(part2,
                                            parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(text,
                                            parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка показа ролей: {e}")
        await update.message.reply_text(
            "⚠️ Отец будет недоволен... Ошибка при получении списка ролей.")


async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        role = execute_supabase_query(
            supabase.table("roles").select("*").eq("user_id", user_id).eq(
                "status", "Бронь"))

        if role:
            role = role[0]
            execute_supabase_query(
                supabase.table("roles").update({
                    "status": "Свободен",
                    "user_id": None,
                    "reserved_until": None
                }).eq("id", role["id"]))
            await update.message.reply_text(
                f"✅ Бронь роли *{role['name']}* снята. Как жаль...",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu())
        else:
            await update.message.reply_text(
                "⚠️ У тебя нет активных броней. Или... ты уже передумал?",
                reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Ошибка отмены брони: {e}")
        await update.message.reply_text(
            "⚠️ Отец хмурится... Ошибка при отмене брони.",
            reply_markup=main_menu())


# ===== ОБРАБОТКА РОЛЕЙ =====
async def start_role_selection(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    try:
        # Устанавливаем московский часовой пояс
        msk_tz = pytz.timezone('Europe/Moscow')
        now_msk = datetime.now(msk_tz)
        current_time = now_msk.time()
        weekday = now_msk.weekday()  # 0-пн, 6-вс

        # Проверка временного интервала (по МСК)
        if (weekday < 6 and not (time(6, 0) <= current_time <= time(19, 0))) or \
           (weekday == 6 and not (time(8, 0) <= current_time <= time(19, 0))):

            await update.message.reply_text(
                "⏳ *Не время для новых участников.*\n\n"
                f"Сейчас в Москве: {now_msk.strftime('%H:%M')}\n\n"
                "Я принимаю заявки только по режиму приема заявок, который ты видимо не прочитал\n"
                "Приходи в указанные часы — и возможно, тебе повезёт.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu())
            return ConversationHandler.END

        # Проверка количества участников
        chat_member_count = await context.bot.get_chat_member_count(CHAT_ID)
        if chat_member_count >= 37:
            await update.message.reply_text(
                "⛔ *Набор закрыт.*\n\n"
                f"Сейчас в чате {chat_member_count}/35 участников.\n"
                "Возвращайся, когда место освободится...",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu())
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка проверки условий: {str(e)}")
        # В случае ошибки разрешаем продолжить с предупреждением
        await update.message.reply_text(
            "⚠️ Я не смог проверить условия. Попробуй ещё раз.",
            reply_markup=main_menu())
        return ConversationHandler.END

    # Если все проверки пройдены
    await update.message.reply_text(
        "Хочешь вступить? Смелый выбор.\nВыбери регион:",
        reply_markup=regions_keyboard())
    return SELECTING_REGION


async def select_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region = update.message.text
    if region == "🔙 Назад в меню":
        await update.message.reply_text("Главное меню:",
                                        reply_markup=main_menu())
        return ConversationHandler.END

    context.user_data['region'] = region
    await update.message.reply_text(
        f"Регион: *{region}*.\nТеперь выбери роль:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=characters_keyboard(region))
    return SELECTING_CHARACTER


async def select_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    character = update.message.text
    if character == "🔙 К регионам":
        await update.message.reply_text("Выбери регион:",
                                        reply_markup=regions_keyboard())
        return SELECTING_REGION

    try:
        role = execute_supabase_query(
            supabase.table("roles").select("*").eq("name", character).eq(
                "region", context.user_data['region']))

        if not role:
            await update.message.reply_text(
                "❌ Персонаж не найден. Попробуй ещё раз.",
                reply_markup=characters_keyboard(context.user_data['region']))
            return SELECTING_CHARACTER

        role = role[0]
        context.user_data['role'] = role

        if role['status'] != "Свободен":
            status_msg = {
                "Бронь": "уже кто-то кусает ногти в ожидании",
                "Занята": "кто-то уже занял"
            }.get(role['status'], "недоступна")

            await update.message.reply_text(
                f"❌ Роль *{character}* {status_msg}. Интересно, надолго ли? Выбирай другую.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=characters_keyboard(context.user_data['region']))
            return SELECTING_CHARACTER

        await update.message.reply_text(
            f"Роль: *{character}*.\n\n"
            "Введи кодовое слово. Да, оно есть в правилах. Нет, я не скажу какое.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove())
        return ENTERING_SECRET_WORD

    except Exception as e:
        logger.error(f"Ошибка выбора персонажа: {e}")
        await update.message.reply_text(
            "⚠️ Отец будет недоволен... Ошибка. Попробуй позже.",
            reply_markup=main_menu())
        return ConversationHandler.END


async def check_secret_word(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    role = context.user_data.get('role')

    if not role:
        await update.message.reply_text("❌ Ошибка. Начни процесс заново.",
                                        reply_markup=main_menu())
        return ConversationHandler.END

    if user_input.lower() == SECRET_WORD.lower():
        try:
            execute_supabase_query(
                supabase.table("roles").update({
                    "status":
                    "Бронь",
                    "user_id":
                    update.effective_user.id,
                    "reserved_until":
                    str(datetime.now() + timedelta(hours=2))
                }).eq("id", role["id"]))

            # Уведомление админа
            if ADMIN_ID:
                try:
                    user = update.effective_user
                    username = f"@{user.username}" if user.username else user.first_name
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=
                        f"🔔 *Новая бронь:*\nПользователь: {username}\nРоль: {role['name']}",
                        parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа: {e}")

            await update.message.reply_text(
                f"✅ Роль *{role['name']}* теперь твоя.\n\n"
                f"Ссылка: {GROUP_LINK}\n\n"
                "⚠️ *У тебя ровно 2 часа:*\n"
                "1. Вступить в чат → или\n"
                "2. Лишиться места → и начинать всё сначала\n\n"
                "Дотторе наблюдает.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu())
        except Exception as e:
            logger.error(f"Ошибка бронирования: {e}")
            await update.message.reply_text(
                "⚠️ Отец хмурится... Ошибка при бронировании.",
                reply_markup=main_menu())
    else:
        await update.message.reply_text(
            "❌ Неверно. Хочешь подсказку? Нет, не хочешь. Читай правила.\n\n"
            "(Введи слово повторно или нажми /cancel)",
            reply_markup=ReplyKeyboardRemove())
        return ENTERING_SECRET_WORD

    return ConversationHandler.END

async def check_expired_bookings(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Получаем текущее время в UTC
        now = datetime.now(pytz.utc).isoformat()

        # Ищем все роли с истёкшей броней
        expired_roles = execute_supabase_query(
            supabase.table("roles")
            .select("*")
            .eq("status", "Бронь")
            .lt("reserved_until", now)  # Ищем записи, где время брони < текущего
        )

        if not expired_roles:
            return

        for role in expired_roles:
            # Освобождаем роль
            execute_supabase_query(
                supabase.table("roles")
                .update({
                    "status": "Свободен",
                    "user_id": None,
                    "reserved_until": None
                })
                .eq("id", role["id"])
            )

            # Уведомляем пользователя (если возможно)
            if role["user_id"]:
                try:
                    await context.bot.send_message(
                        chat_id=role["user_id"],
                        text=f"⌛ Ваша бронь роли *{role['name']}* истекла. Хотите повторить?",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить пользователя {role['user_id']}: {e}")

        logger.info(f"Освобождено {len(expired_roles)} просроченных броней")

    except Exception as e:
        logger.error(f"Ошибка при проверке броней: {e}")
        await notify_admin(f"⚠️ Ошибка проверки броней: {str(e)}", context)

# ===== АДМИН-ФУНКЦИИ =====
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != "coffeefin" and user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав доступа к этой команде.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("🔐 Админ-панель:", reply_markup=admin_inline_keyboard())
    return ADMIN_PANEL


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Обязательно подтверждаем callback

    logger.info(f"Админ панель: получен callback - {query.data}")  # Логируем

    try:
        if query.data == "admin_swap":
            context.user_data.clear()
            await query.edit_message_text(
                "🔄 <b>Обмен ролями</b>\nВведите имя ПЕРВОЙ роли:",
                parse_mode=ParseMode.HTML
            )
            return SWAP_ROLES_FIRST

        elif query.data == "admin_change_status":
            context.user_data.clear()
            await query.edit_message_text(
                "🔄 <b>Изменение статуса</b>\nВведите имя роли:",
                parse_mode=ParseMode.HTML
            )
            return FORCE_CHANGE_ROLE_SELECT

        elif query.data == "admin_free":
            context.user_data.clear()
            await query.edit_message_text(
                "🔓 <b>Освобождение роли</b>\nВведите имя роли:",
                parse_mode=ParseMode.HTML
            )
            return FORCE_CHANGE_ROLE_SELECT

        elif query.data == "admin_add_role":
            context.user_data.clear()
            await query.edit_message_text(
                "➕ <b>Добавление роли</b>\nВведите имя новой роли:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")]]
                )
            )
            return ADD_ROLE_NAME

        elif query.data == "admin_delete_role":
            context.user_data.clear()
            await query.edit_message_text(
                "🗑 <b>Удаление роли</b>\nВведите имя роли для удаления:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")]]
                )
            )
            return DELETE_ROLE_SELECT

        elif query.data == "admin_current":
            roles_data = execute_supabase_query(
                supabase.table("roles").select("name, user_id, status").neq("status", "Свободен")
            )

            if not roles_data:
                await query.edit_message_text(
                    "ℹ️ Нет занятых ролей.",
                    reply_markup=admin_inline_keyboard()
                )
                return ADMIN_PANEL

            text = "<b>📋 Текущие занятые роли:</b>\n\n"
            for role in roles_data:
                status_emoji = STATUS_EMOJI.get(role['status'], '⚪')
                text += f"{status_emoji} <b>{role['name']}</b> - "

                if role['user_id']:
                    try:
                        user = await context.bot.get_chat(role['user_id'])
                        username = f"@{user.username}" if user.username else user.first_name
                        text += f"{username}\n"
                    except Exception as e:
                        text += "Неизвестный пользователь\n"
                        logger.error(f"Ошибка получения пользователя: {e}")
                else:
                    text += "Нет пользователя\n"

            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_inline_keyboard()
            )
            return ADMIN_PANEL

        elif query.data.startswith("status_"):
            role = context.user_data.get('role_to_change')
            if not role:
                await query.edit_message_text(
                    "❌ Ошибка: данные роли утеряны",
                    reply_markup=admin_inline_keyboard()
                )
                return ADMIN_PANEL

            status_map = {
                "status_free": ("Свободен", None),
                "status_reserved": ("Бронь", str(datetime.now() + timedelta(hours=2))),
                "status_taken": ("Занята", None)
            }

            status_name, reserved_until = status_map.get(query.data, (None, None))

            if not status_name:
                await query.edit_message_text(
                    "❌ Неизвестный статус",
                    reply_markup=admin_inline_keyboard()
                )
                return ADMIN_PANEL

            try:
                update_data = {"status": status_name, "reserved_until": reserved_until}

                if status_name != "Свободен":
                    update_data["user_id"] = role.get("user_id")

                execute_supabase_query(
                    supabase.table("roles")
                    .update(update_data)
                    .eq("id", role["id"])
                )

                await query.edit_message_text(
                    f"✅ Статус роли <b>{role['name']}</b> изменен на: {status_name}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=admin_inline_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка изменения статуса: {e}")
                await query.edit_message_text(
                    "⚠️ Ошибка при изменении статуса",
                    reply_markup=admin_inline_keyboard()
                )
            return ADMIN_PANEL

        elif query.data == "confirm_add_role":
            return await confirm_add_role(update, context)

        elif query.data == "confirm_delete_role":
            return await confirm_delete_role(update, context)

        elif query.data == "admin_cancel":
            await query.edit_message_text(
                "❌ Действие отменено",
                reply_markup=admin_inline_keyboard()
            )
            return ADMIN_PANEL

        else:
            logger.warning(f"Неизвестный callback_data: {query.data}")
            await query.edit_message_text(
                "⚠️ Неизвестная команда",
                reply_markup=admin_inline_keyboard()
            )
            return ADMIN_PANEL

    except Exception as e:
        logger.error(f"Ошибка в admin_button_handler: {str(e)}")
        await query.edit_message_text(
            "⚠️ Произошла ошибка. Попробуйте снова.",
            reply_markup=admin_inline_keyboard()
        )
        return ADMIN_PANEL


async def handle_swap_roles_first(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    role_name = update.message.text
    role = execute_supabase_query(
        supabase.table("roles").select("*").eq("name", role_name))

    if not role:
        await update.message.reply_text("❌ Роль не найдена")
        return SWAP_ROLES_FIRST

    context.user_data['first_role'] = role[0]
    await update.message.reply_text("Введите имя ВТОРОЙ роли для обмена:")
    return SWAP_ROLES_SECOND


async def handle_swap_roles_second(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    second_role_name = update.message.text
    first_role = context.user_data.get('first_role')

    if not first_role:
        await update.message.reply_text("❌ Первая роль не найдена")
        return ADMIN_PANEL

    second_role = execute_supabase_query(
        supabase.table("roles").select("*").eq("name", second_role_name))

    if not second_role:
        await update.message.reply_text("❌ Роль не найдена")
        return SWAP_ROLES_SECOND

    second_role = second_role[0]

    # Выполняем обмен
    execute_supabase_query(
        supabase.table("roles").update({
            "user_id": second_role["user_id"],
            "status": second_role["status"]
        }).eq("id", first_role["id"]))

    execute_supabase_query(
        supabase.table("roles").update({
            "user_id": first_role["user_id"],
            "status": first_role["status"]
        }).eq("id", second_role["id"]))

    await update.message.reply_text(
        f"✅ Роли обменяны:\n"
        f"{first_role['name']} ↔ {second_role['name']}",
        reply_markup=admin_inline_keyboard())
    return ADMIN_PANEL


async def handle_select_role_for_status(update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
    role_name = update.message.text
    role = execute_supabase_query(
        supabase.table("roles").select("*").eq("name", role_name))

    if not role:
        await update.message.reply_text("❌ Роль не найдена")
        return FORCE_CHANGE_ROLE_SELECT

    context.user_data['role_to_change'] = role[0]
    await update.message.reply_text(
        f"Выберите новый статус для роли {role_name}:",
        reply_markup=status_inline_keyboard())
    return FORCE_CHANGE_ROLE_STATUS


async def handle_select_role_for_free(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
    role_name = update.message.text
    role = execute_supabase_query(
        supabase.table("roles").select("*").eq("name", role_name))

    if not role:
        await update.message.reply_text("❌ Роль не найдена")
        return FORCE_CHANGE_ROLE_SELECT

    role = role[0]
    user_id = role["user_id"]

    execute_supabase_query(
        supabase.table("roles").update({
            "status": "Свободен",
            "user_id": None,
            "reserved_until": None
        }).eq("id", role["id"]))

    if user_id:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Администратор снял вашу бронь роли {role['name']}",
                parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(
                f"Ошибка отправки уведомления пользователю {user_id}: {e}")

    await update.message.reply_text(f"✅ Роль {role['name']} освобождена!",
                                    reply_markup=admin_inline_keyboard())
    return ADMIN_PANEL

async def add_role_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role_name = update.message.text
    existing_role = execute_supabase_query(
        supabase.table("roles").select("*").eq("name", role_name)
    )

    if existing_role:
        await update.message.reply_text(
            "❌ Роль с таким именем уже существует! Введите другое имя:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")]])
        )
        return ADD_ROLE_NAME

    context.user_data['new_role'] = {'name': role_name}
    await update.message.reply_text(
        "Введите регион для новой роли (Мондштадт, Ли Юэ, Инадзума и т.д.):",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADD_ROLE_REGION

async def add_role_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region = update.message.text
    context.user_data['new_role']['region'] = region
    role = context.user_data['new_role']

    await update.message.reply_text(
        f"Подтвердите создание роли:\n\n"
        f"Имя: {role['name']}\n"
        f"Регион: {role['region']}\n\n"
        f"Статус: Свободен (по умолчанию)",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_add_role")],
            [InlineKeyboardButton("❌ Отменить", callback_data="admin_cancel")]
        ])
    )
    return ADD_ROLE_CONFIRM

async def confirm_add_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    role = context.user_data['new_role']

    try:
        execute_supabase_query(
            supabase.table("roles").insert({
                "name": role['name'],
                "region": role['region'],
                "status": "Свободен",
                "user_id": None,
                "reserved_until": None
            })
        )
        await query.edit_message_text(
            f"✅ Роль {role['name']} успешно добавлена!",
            reply_markup=admin_inline_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка добавления роли: {e}")
        await query.edit_message_text(
            "⚠️ Ошибка при добавлении роли. Проверьте логи.",
            reply_markup=admin_inline_keyboard()
        )

    return ADMIN_PANEL

async def delete_role_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод имени роли для удаления и запрашивает подтверждение.
    """
    role_name_to_delete = update.message.text
    # Здесь можно добавить логику проверки, существует ли такая роль в вашей базе данных
    role = execute_supabase_query(supabase.table("roles").select("*").eq("name", role_name_to_delete)) # 
    if not role:
        await update.message.reply_text(
            f"❌ Роль '{role_name_to_delete}' не найдена. Пожалуйста, введите корректное имя роли или нажмите Отмена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" ❌   Отмена ", callback_data="admin_cancel")]]) # 
        )
        return DELETE_ROLE_SELECT # Остаемся в этом состоянии, пока не получим корректное имя или отмену

    context.user_data['role_to_delete'] = role[0] # Сохраняем информацию о роли для подтверждения

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Подтвердить удаление '{role_name_to_delete}'", callback_data="confirm_delete_role")], # 
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")] # 
    ])
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить роль '{role_name_to_delete}'? Это действие необратимо!",
        reply_markup=keyboard
    )
    return CONFIRM_DELETE_ROLE # Переходим в состояние ожидания подтверждения

async def confirm_delete_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выполняет удаление роли после подтверждения.
    Эта функция вызывается из admin_button_handler.
    """
    query = update.callback_query
    await query.answer()

    role_to_delete = context.user_data.get('role_to_delete')
    if not role_to_delete:
        await query.edit_message_text(
            "❌ Ошибка: Роль для удаления не найдена в контексте. Начните заново.",
            reply_markup=admin_inline_keyboard() # 
        )
        return ADMIN_PANEL

    try:
        # Выполняем удаление из базы данных Supabase
        execute_supabase_query(supabase.table("roles").delete().eq("id", role_to_delete["id"])) # 

        await query.edit_message_text(
            f"✅ Роль '{role_to_delete['name']}' успешно удалена.",
            reply_markup=admin_inline_keyboard() # 
        )
    except Exception as e:
        logger.error(f"Ошибка при удалении роли {role_to_delete['name']}: {e}") # 
        await query.edit_message_text(
            f"⚠ Ошибка при удалении роли '{role_to_delete['name']}'. Попробуйте снова.",
            reply_markup=admin_inline_keyboard() # 
        )
    finally:
        # Очищаем данные пользователя после завершения операции
        if 'role_to_delete' in context.user_data:
            del context.user_data['role_to_delete']

    return ADMIN_PANEL # Возвращаемся в админ-панель

async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 Админ-панель:",
                                    reply_markup=admin_inline_keyboard())
    return ADMIN_PANEL


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=main_menu())
    return ConversationHandler.END


async def cancel_conversation(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=main_menu()
        if update.effective_chat.type == "private" else None)
    return ConversationHandler.END


# ===== ОБРАБОТКА УЧАСТНИКОВ =====
async def handle_participant_update(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.chat_member:
            await process_chat_member_change(update.chat_member, context)
        elif update.message:
            if update.message.new_chat_members:
                for user in update.message.new_chat_members:
                    await process_new_member(user, update.message.chat,
                                             context)
            elif update.message.left_chat_member:
                await process_left_member(update.message.left_chat_member,
                                          update.message.chat, context)
    except Exception as e:
        logger.error(f"Ошибка обработки участника: {e}")
        await notify_admin(f"Ошибка обработки участника: {e}", context)


async def process_chat_member_change(chat_member: ChatMemberUpdated,
                                     context: ContextTypes.DEFAULT_TYPE):
    if chat_member.chat.id != CHAT_ID:
        return

    old = chat_member.old_chat_member
    new = chat_member.new_chat_member
    user = new.user

    if (new.status == ChatMemberStatus.MEMBER and old.status not in [
            ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
    ]):
        await process_new_member(user, chat_member.chat, context)
    elif (new.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
          and old.status in [
              ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR,
              ChatMemberStatus.OWNER
          ]):
        await process_left_member(user, chat_member.chat, context)


async def process_new_member(user: User, chat: Chat,
                             context: ContextTypes.DEFAULT_TYPE):
    if user.id == context.bot.id:
        return

    role = execute_supabase_query(
        supabase.table("roles").select("*").eq("user_id", user.id).neq(
            "status", "Свободен"))

    if role:
        role = role[0]
        execute_supabase_query(
            supabase.table("roles").update({
                "status": "Занята",
                "reserved_until": None
            }).eq("id", role["id"]))

        await context.bot.send_message(
            chat_id=chat.id,
            text=
            f"✅ {user.mention_html()} подтвердил роль <b>{role['name']}</b>. Отец доволен.",
            parse_mode=ParseMode.HTML)
    else:
        warning_text = (
            f"🚨 Тревога! {user.mention_html()} ворвался без брони! "
            f"Отец, вернись в чат {ADMIN_USERNAME}")

        await context.bot.send_message(chat_id=chat.id,
                                       text=warning_text,
                                       parse_mode=ParseMode.HTML)

        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚨 Неверифицированный участник: {user.mention_html()}",
                parse_mode=ParseMode.HTML)


async def process_left_member(user: User, chat: Chat,
                              context: ContextTypes.DEFAULT_TYPE):
    role = execute_supabase_query(
        supabase.table("roles").select("*").eq("user_id",
                                               user.id).eq("status", "Занята"))

    if role:
        role = role[0]
        execute_supabase_query(
            supabase.table("roles").update({
                "status":
                "Бронь",
                "reserved_until":
                str(datetime.now() + timedelta(hours=24))
            }).eq("id", role["id"]))

        await notify_admin(
            f"⚠️ Пользователь {user.mention_html()} вышел. Роль {role['name']} на брони 24ч.",
            context)


async def handle_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех сообщений в чате для ответов Клифа"""
    try:
        # Игнорируем сообщения от ботов
        if update.effective_user.is_bot:
            return

        # Сначала проверяем команды администратора
        admin_response = await handle_admin_commands(update, context)
        if admin_response:
            await update.message.reply_text(admin_response)
            return

        # Затем проверяем обращения к Клифу
        cliff_response = await handle_direct_mention(update, context)
        if cliff_response:
            await update.message.reply_text(cliff_response)
            return

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")


# ===== НАСТРОЙКА ОБРАБОТЧИКОВ =====
def setup_role_selection_conversation():
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("⋄┋ⲬⲞⳠⲨ ⲂⲤⲦⲨⲠⳘⲦЬ┋⋄"),
                           start_role_selection)
        ],
        states={
            SELECTING_REGION:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, select_region)],
            SELECTING_CHARACTER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               select_character)
            ],
            ENTERING_SECRET_WORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               check_secret_word)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)])


def setup_admin_conversation():
    return ConversationHandler(
        entry_points=[CommandHandler('admin', admin_command)],
        states={
            ADMIN_PANEL: [
                CallbackQueryHandler(admin_button_handler)
            ],
            SWAP_ROLES_FIRST: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_swap_roles_first
                )
            ],
            SWAP_ROLES_SECOND: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_swap_roles_second
                )
            ],
            FORCE_CHANGE_ROLE_SELECT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_select_role_for_status
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_select_role_for_free
                )
            ],
            FORCE_CHANGE_ROLE_STATUS: [
                CallbackQueryHandler(
                    admin_button_handler,
                    pattern="^status_"
                )
            ],
            ADD_ROLE_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_role_name
                )
            ],
            ADD_ROLE_REGION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_role_region
                )
            ],
            ADD_ROLE_CONFIRM: [
                CallbackQueryHandler(
                    admin_button_handler,
                    pattern="^confirm_add_role$"
                ),
                CallbackQueryHandler(
                    admin_button_handler,
                    pattern="^admin_cancel$"
                )
            ],
            DELETE_ROLE_SELECT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    delete_role_select
                )
            ],
            CONFIRM_DELETE_ROLE: [
                CallbackQueryHandler(
                    admin_button_handler,
                    pattern="^confirm_delete_role$"
                ),
                CallbackQueryHandler(
                    admin_button_handler,
                    pattern="^admin_cancel$"
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_conversation),
            MessageHandler(
                filters.Regex(r'^🔙 Назад в меню$'),
                back_to_menu
            )
        ],
        allow_reentry=True  # Разрешаем повторный вход в диалог
    )


def test_apis():
    print("🔍 Тестирование подключений...")
    try:
        # Тест Telegram API
        from telegram import __version__
        print(f"Telegram API: OK (v{__version__})")

        # Тест реального Supabase (только если переменные окружения установлены)
        if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_KEY'):
            print("Supabase: проверка подключения...")
            # Создаем клиент с реальными данными, но не выполняем запросы
            supabase = create_client(os.environ['SUPABASE_URL'],
                                     os.environ['SUPABASE_KEY'])
            print("Supabase: подключение успешно")
        else:
            print(
                "Supabase: переменные окружения не найдены (пропускаем проверку)"
            )

    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        raise

# ===== ЗАПУСК БОТА =====
def main():
    try:
        logger.info("🟢 Запуск бота и веб-сервера...")

        # Запуск веб-сервера в отдельном потоке
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        logger.info("🟢 Веб-сервер запущен")

        # Инициализация бота
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        logger.info("🟢 Бот инициализирован")

        # Добавляем фоновую задачу (проверка каждые 10 минут)
        telegram_app.job_queue.run_repeating(
            check_expired_bookings,
            interval=600,  # 10 минут в секундах
            first=10       # Первый запуск через 10 сек после старта
        )

        # 1. Основные команды
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("help", show_help))
        telegram_app.add_handler(CommandHandler("admin", admin_command)) 
        telegram_app.add_handler(CommandHandler("cancel_booking", cancel_booking))

        # 2. Обработчики кнопок
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲡⲣⲁⲃυⲗⲁ┋⋄"), show_rules))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲣⲟⲗυ┋⋄"), show_roles))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲣⲉⲯυⲙ ⲡⲣυⲉⲙⲁ ⳅⲁяⲃⲟⲕ┋⋄"), show_regime))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲡⲟⲙⲟⳃь┋⋄"), show_help))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲏⲁⲱ ⲦⲓⲕⲦⲟⲕ┋⋄"), show_tiktok))

        # 3. Диалоговые обработчики
        telegram_app.add_handler(setup_role_selection_conversation())
        telegram_app.add_handler(setup_admin_conversation())
        telegram_app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            handle_answers,
        ))

        # 4. Обработчики участников
        telegram_app.add_handler(ChatMemberHandler(handle_participant_update))
        telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_participant_update))
        telegram_app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_participant_update))

        logger.info("🟢 Бот запущен")
        telegram_app.run_polling()

    except Exception as e:
        logger.critical(f"🔴 Критическая ошибка: {e}")
        raise  # Добавим raise чтобы видеть traceback


logging.basicConfig(filename='bot.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(message)s')


def auto_clean_memory():
    import gc
    while True:
        gc.collect()
        std_time.sleep(3600)  # используем переименованный модуль

@app.route('/ping')
def ping():
    logger.info("Сервер получил запрос на /ping")
    return "Сервер работает! ✅"

@app.route('/uptime')
def uptime_check():
    return jsonify({"status": "OK", "bot": "active"}), 200

def self_ping():
    while True:
        try:
            url = "https://19a05b27-e552-4557-a606-6cf696041329-00-3rt5hv6j3qqnl.kirk.replit.dev:8080/"
            requests.get(url, timeout=5)
            print(f"✅ Самопинг успешен: {url}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        std_time.sleep(25 * 60 + random.randint(-120, 120))

if __name__ == '__main__':
    try:
        # Инициализация бота
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        logger.info("🟢 Бот инициализирован")

        # Добавляем фоновую задачу (проверка каждые 10 минут)
        telegram_app.job_queue.run_repeating(
            check_expired_bookings,
            interval=600,
            first=10
        )

        # Обработчики команд (ваш код без изменений)
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("help", show_help))
        telegram_app.add_handler(CommandHandler("admin", admin_command)) 
        telegram_app.add_handler(CommandHandler("cancel_booking", cancel_booking))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲡⲣⲁⲃυⲗⲁ┋⋄"), show_rules))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲣⲟⲗυ┋⋄"), show_roles))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲣⲉⲯυⲙ ⲡⲣυⲉⲙⲁ ⳅⲁяⲃⲟⲕ┋⋄"), show_regime))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲡⲟⲙⲟⳃь┋⋄"), show_help))
        telegram_app.add_handler(MessageHandler(filters.Regex(r"⋄┋ⲏⲁⲱ ⲦⲓⲕⲦⲟⲕ┋⋄"), show_tiktok))
        telegram_app.add_handler(setup_role_selection_conversation())
        telegram_app.add_handler(setup_admin_conversation())
        telegram_app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            handle_answers,
        ))
        telegram_app.add_handler(ChatMemberHandler(handle_participant_update))
        telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_participant_update))
        telegram_app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_participant_update))

        logger.info("🟢 Бот запущен")
        
        # Запуск бота в режиме polling (для Railway)
        telegram_app.run_polling()

    except Exception as e:
        logger.critical(f"🔴 Критическая ошибка: {e}")
