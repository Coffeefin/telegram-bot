# Стандартные библиотеки Python
import logging
import os
from datetime import datetime, time, timedelta
import pytz

from telegram import CallbackQuery
from keep_alive import keep_alive
from answers import handle_direct_mention

# Telegram Bot API
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove,
                      ChatMemberUpdated, Chat, User)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters, ConversationHandler,
                          CallbackQueryHandler, ChatMemberHandler)

from supabase import create_client

from config import supabase, execute_supabase_query, ADMIN_ID

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

# Константы
CHAT_ID = -1002360670599
ADMIN_USERNAME = "@coffeefin"
SECRET_WORD = "Вино"
GROUP_LINK = "https://t.me/+ODPMk-Js4ik4OWRi"
TIKTOK_URL = "https://www.tiktok.com/@expcham_flood"
RULES_TEXT = "📜 **Отец терпеть не может нарушителей.**\nКоротко: не спамьте, не спорьте, активьте.\nА ещё — найди кодовое слово. Оно понадобится... очень скоро.\n\nПодробности: telegra.ph/Pravila-07-06-183"
REGIME_TEXT = "⏰ **Режим приема заявок:**\n◈ ПН-СБ — 09:00-19:00 (МСК)\n◈ ВС — 10:00-19:00 (МСК)\n\nСистема автоматически отклоняет заявки вне этого окна. Даже не пытайся обойти — я слежу."
HELP_TEXT = """
🆘 <b>Помощь:</b>
▪️ Проблемы с ботом → @HelpSuupp_bot
▪️ Недоразумения → @HelpSuupp_bot
▪️ Вопросы без ответов → @HelpSuupp_bot
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
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🔀 Поменять ролями",
                                 callback_data="admin_swap"),
            InlineKeyboardButton("🔄 Изменить статус",
                                 callback_data="admin_change_status")
        ],
         [
             InlineKeyboardButton("🔓 Освободить роль",
                                  callback_data="admin_free"),
             InlineKeyboardButton("➕ Добавить роль",
                                  callback_data="admin_add_role")
         ],
         [
             InlineKeyboardButton("🗑 Удалить роль",
                                  callback_data="admin_delete_role"),
             InlineKeyboardButton("📋 Текущие роли",
                                  callback_data="admin_current")
         ]])


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
            f"Добро пожаловать, {user.mention_html()}.\n\n"
            "Я - Клиф. Если коротко: я тот, кто решает, кто проходит в чат, а кто остаётся за дверью. "
            "Моя работа - провести тебя через все формальности, чтобы ты мог(ла) присоединиться к нам, как положено.\n\n"
            "📜 Сначала изучи:\n"
            "1. Правила (отец терпеть не может нарушителей)\n"
            "2. Список ролей\n"
            "3. График приёма (мы тоже любим поспать)\n\n"
            "Когда изучишь материалы — жми «Хочу вступить» и следуй инструкциям.",
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
    user_id = update.effective_user.id

    # Проверяем, есть ли у пользователя активная роль
    active_role = execute_supabase_query(
        supabase.table("roles").select("*").or_(
            "status.eq.Бронь,status.eq.Занята").eq("user_id", user_id))

    if active_role:
        role = active_role[0]
        await update.message.reply_text(
            f"⛔ У вас уже есть активная роль: *{role['name']}* (статус: {role['status']}).\n"
            "Вы не можете забронировать новую роль, пока текущая активна.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu())
        return ConversationHandler.END

    try:
        # Устанавливаем московский часовой пояс
        msk_tz = pytz.timezone('Europe/Moscow')
        now_msk = datetime.now(msk_tz)
        current_time = now_msk.time()
        weekday = now_msk.weekday()  # 0-пн, 6-вс

        # Проверка временного интервала (по МСК)
        if (weekday < 6 and not (time(9, 0) <= current_time <= time(19, 0))) or \
           (weekday == 6 and not (time(10, 0) <= current_time <= time(19, 0))):

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
        await update.message.reply_text(
            "⚠️ Я не смог проверить условия. Попробуй ещё раз.",
            reply_markup=main_menu())
        return ConversationHandler.END

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
                f"✅ Роль <b>{role['name']}</b> теперь твоя.\n\n"
                f"Ссылка: {GROUP_LINK}\n\n"
                "⚠️ <b>У тебя ровно 2 часа на то, чтобы вступить в чат, иначе придется начинать процедуру сначала</b>\n"
                "Хочешь отменить бронь? Нажимай /cancel_booking",
                parse_mode=ParseMode.HTML,
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
        now = datetime.now(pytz.utc)

        # Получаем все брони
        roles = execute_supabase_query(
            supabase.table("roles").select("*").eq("status", "Бронь"))

        if not roles:
            return

        for role in roles:
            reserved_until = datetime.fromisoformat(
                role["reserved_until"]).replace(tzinfo=pytz.utc)
            time_left = reserved_until - now

            # Если время вышло
            if time_left.total_seconds() <= 0:
                execute_supabase_query(
                    supabase.table("roles").update({
                        "status": "Свободен",
                        "user_id": None,
                        "reserved_until": None
                    }).eq("id", role["id"]))

                if role["user_id"]:
                    try:
                        await context.bot.send_message(
                            chat_id=role["user_id"],
                            text=
                            f"⌛ Ваша бронь роли *{role['name']}* истекла. Хотите повторить?",
                            parse_mode=ParseMode.MARKDOWN)
                    except Exception as e:
                        logger.error(
                            f"Не удалось уведомить пользователя {role['user_id']}: {e}"
                        )

            # Уведомления за 1 час, 30 минут и 5 минут
            elif role["user_id"]:
                notification_text = None

                if timedelta(minutes=5) < time_left <= timedelta(minutes=30):
                    if time_left <= timedelta(
                            minutes=30) and not role.get("notified_30min"):
                        notification_text = f"⏳ До окончания брони роли *{role['name']}* осталось 30 минут.\n/cancel_booking - если передумали"
                        execute_supabase_query(
                            supabase.table("roles").update({
                                "notified_30min":
                                True
                            }).eq("id", role["id"]))

                elif timedelta(minutes=1) < time_left <= timedelta(minutes=5):
                    if time_left <= timedelta(
                            minutes=5) and not role.get("notified_5min"):
                        notification_text = f"⏳ До окончания брони роли *{role['name']}* осталось 5 минут!\n/cancel_booking - если передумали"
                        execute_supabase_query(
                            supabase.table("roles").update({
                                "notified_5min":
                                True
                            }).eq("id", role["id"]))

                elif time_left <= timedelta(
                        hours=1) and not role.get("notified_1hour"):
                    notification_text = f"⏳ До окончания брони роли *{role['name']}* остался 1 час.\n/cancel_booking - если передумали"
                    execute_supabase_query(
                        supabase.table("roles").update({
                            "notified_1hour": True
                        }).eq("id", role["id"]))

                if notification_text and role["user_id"]:
                    try:
                        await context.bot.send_message(
                            chat_id=role["user_id"],
                            text=notification_text,
                            parse_mode=ParseMode.MARKDOWN)
                    except Exception as e:
                        logger.error(
                            f"Не удалось уведомить пользователя {role['user_id']}: {e}"
                        )

    except Exception as e:
        logger.error(f"Ошибка при проверке броней: {e}")


# ===== АДМИН-ФУНКЦИИ =====
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        logger.warning(
            f"Попытка доступа к админ-панели от неавторизованного пользователя: {user.username} (ID: {user.id})"
        )
        await update.message.reply_text(
            "⛔ У вас нет прав доступа к этой команде.")
        return ConversationHandler.END

    logger.info(f"Админ-панель открыта пользователем: {user.username}")
    context.user_data.clear()
    await update.message.reply_text("🔐 Админ-панель:",
                                    reply_markup=admin_inline_keyboard())
    return ADMIN_PANEL


async def show_current_roles(query: CallbackQuery,
                             context: ContextTypes.DEFAULT_TYPE):
    try:
        roles = execute_supabase_query(
            supabase.table("roles").select("*").or_(
                "status.eq.Бронь,status.eq.Занята").order("region").order(
                    "name"))

        if not roles:
            await query.edit_message_text("❌ Нет активных ролей.",
                                          reply_markup=admin_inline_keyboard())
            return ADMIN_PANEL

        text = "📋 <b>Активные роли (Бронь/Занята):</b>\n\n"
        for role in roles:
            emoji = STATUS_EMOJI.get(role["status"], "⚪")
            user_info = ""
            if role["user_id"]:
                try:
                    user = await context.bot.get_chat(role["user_id"])
                    user_info = f" (@{user.username})" if user.username else f" (ID: {user.id})"
                except Exception as e:
                    user_info = f" (ID: {role['user_id']})"
                    logger.error(
                        f"Ошибка получения информации о пользователе: {e}")

            text += f"{emoji} <code>{role['name']}</code> — {role['status']}{user_info}\n"

        await query.edit_message_text(text,
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=admin_inline_keyboard())
        return ADMIN_PANEL
    except Exception as e:
        logger.error(f"Ошибка в show_current_roles: {e}")
        await query.edit_message_text("⚠️ Ошибка загрузки ролей.",
                                      reply_markup=admin_inline_keyboard())
        return ADMIN_PANEL


async def admin_button_handler(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"Обработка callback: {data}")

    try:
        if data == "admin_swap":
            await query.edit_message_text(
                "🔄 <b>Обмен ролями</b>\nВведите имя ПЕРВОЙ роли:",
                parse_mode=ParseMode.HTML)
            return SWAP_ROLES_FIRST

        elif data == "admin_change_status":
            await query.edit_message_text(
                "🔄 <b>Изменение статуса</b>\nВведите имя роли:",
                parse_mode=ParseMode.HTML)
            return FORCE_CHANGE_ROLE_SELECT

        elif data == "admin_free":
            await query.edit_message_text(
                "🔓 <b>Освобождение роли</b>\nВведите имя роли:",
                parse_mode=ParseMode.HTML)
            return FORCE_CHANGE_ROLE_SELECT

        elif data == "admin_add_role":
            await query.edit_message_text(
                "➕ <b>Добавление роли</b>\nВведите имя новой роли:",
                parse_mode=ParseMode.HTML)
            return ADD_ROLE_NAME

        elif data == "admin_delete_role":
            await query.edit_message_text(
                "🗑 <b>Удаление роли</b>\nВведите имя роли для удаления:",
                parse_mode=ParseMode.HTML)
            return DELETE_ROLE_SELECT

        elif data == "admin_current":
            return await show_current_roles(query, context)

        elif data.startswith("status_"):
            role = context.user_data.get('role_to_change')
            if not role:
                await query.edit_message_text(
                    "❌ Роль не выбрана", reply_markup=admin_inline_keyboard())
                return ADMIN_PANEL

            new_status = data.replace("status_", "").capitalize()

            # Для освобождения роли (статус "Свободен")
            if new_status == "Free":  # Если callback_data был "status_free"
                new_status = "Свободен"
                update_data = {
                    "status": new_status,
                    "user_id": None,
                    "reserved_until": None
                }
            else:
                update_data = {"status": new_status}

            execute_supabase_query(
                supabase.table("roles").update(update_data).eq(
                    "id", role["id"]))

            await query.edit_message_text(
                f"✅ Статус роли {role['name']} изменён на {new_status}",
                reply_markup=admin_inline_keyboard())
            return ADMIN_PANEL

        elif data == "confirm_add_role":
            return await confirm_add_role(update, context)

        elif data == "confirm_delete_role":
            return await confirm_delete_role(update, context)

        elif data == "admin_cancel":
            await query.edit_message_text("❌ Действие отменено",
                                          reply_markup=admin_inline_keyboard())
            return ADMIN_PANEL

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {str(e)}")
        await query.edit_message_text("⚠️ Произошла ошибка. Попробуйте снова.",
                                      reply_markup=admin_inline_keyboard())
        return ADMIN_PANEL


async def handle_admin_message(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    current_state = await context.application.persistence.get_conversation(
        update.effective_chat.id, update.effective_user.id)
    logger.info(
        f"Получено сообщение в состоянии {current_state}: {update.message.text}"
    )

    if current_state == SWAP_ROLES_FIRST:
        return await handle_swap_roles_first(update, context)
    elif current_state == SWAP_ROLES_SECOND:
        return await handle_swap_roles_second(update, context)
    elif current_state == FORCE_CHANGE_ROLE_SELECT:
        return await handle_select_role_for_status(update, context)
    elif current_state == ADD_ROLE_NAME:
        return await add_role_name(update, context)
    elif current_state == ADD_ROLE_REGION:
        return await add_role_region(update, context)
    elif current_state == DELETE_ROLE_SELECT:
        return await delete_role_select(update, context)

    await update.message.reply_text(
        "Неизвестная команда. Используйте кнопки админ-панели.",
        reply_markup=admin_inline_keyboard())
    return ADMIN_PANEL


async def handle_swap_roles_first(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    print("📥 Получено сообщение в SWAP_ROLES_FIRST:", update.message.text)
    logger.info("📥 Получено сообщение в SWAP_ROLES_FIRST: %s",
                update.message.text)

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
        supabase.table("roles").select("*").eq("name", role_name))

    if existing_role:
        await update.message.reply_text(
            "❌ Роль с таким именем уже существует! Введите другое имя:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")
            ]]))
        return ADD_ROLE_NAME

    context.user_data['new_role'] = {'name': role_name}
    await update.message.reply_text(
        "Введите регион для новой роли (Мондштадт, Ли Юэ, Инадзума и т.д.):",
        reply_markup=ReplyKeyboardRemove())
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
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Подтвердить",
                                 callback_data="confirm_add_role")
        ], [InlineKeyboardButton("❌ Отменить",
                                 callback_data="admin_cancel")]]))
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
            }))
        await query.edit_message_text(
            f"✅ Роль {role['name']} успешно добавлена!",
            reply_markup=admin_inline_keyboard())
    except Exception as e:
        logger.error(f"Ошибка добавления роли: {e}")
        await query.edit_message_text(
            "⚠️ Ошибка при добавлении роли. Проверьте логи.",
            reply_markup=admin_inline_keyboard())

    return ADMIN_PANEL


async def delete_role_select(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    role_name_to_delete = update.message.text
    role = execute_supabase_query(
        supabase.table("roles").select("*").eq("name", role_name_to_delete))
    if not role:
        await update.message.reply_text(
            f"❌ Роль '{role_name_to_delete}' не найдена. Пожалуйста, введите корректное имя роли или нажмите Отмена.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(" ❌   Отмена ",
                                     callback_data="admin_cancel")
            ]]))
        return DELETE_ROLE_SELECT

    context.user_data['role_to_delete'] = role[0]

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Подтвердить удаление '{role_name_to_delete}'",
                             callback_data="confirm_delete_role")
    ], [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")]])
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить роль '{role_name_to_delete}'? Это действие необратимо!",
        reply_markup=keyboard)
    return CONFIRM_DELETE_ROLE


async def confirm_delete_role(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    role_to_delete = context.user_data.get('role_to_delete')
    if not role_to_delete:
        await query.edit_message_text(
            "❌ Ошибка: Роль для удаления не найдена в контексте. Начните заново.",
            reply_markup=admin_inline_keyboard())
        return ADMIN_PANEL

    try:
        execute_supabase_query(
            supabase.table("roles").delete().eq("id", role_to_delete["id"]))

        await query.edit_message_text(
            f"✅ Роль '{role_to_delete['name']}' успешно удалена.",
            reply_markup=admin_inline_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при удалении роли {role_to_delete['name']}: {e}")
        await query.edit_message_text(
            f"⚠ Ошибка при удалении роли '{role_to_delete['name']}'. Попробуйте снова.",
            reply_markup=admin_inline_keyboard())
    finally:
        if 'role_to_delete' in context.user_data:
            del context.user_data['role_to_delete']

    return ADMIN_PANEL


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
            f"✅ {user.mention_html()} подтвердил роль <b>{role['name']}</b>.",
            parse_mode=ParseMode.HTML)

        # Уведомление админа
        if ADMIN_ID:
            username = f"@{user.username}" if user.username else user.first_name
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=
                f"🔔 Пользователь {username} вошёл в чат с ролью {role['name']}",
                parse_mode=ParseMode.HTML)
    else:
        warning_text = f"🚨 Тревога! {user.mention_html()} ворвался без брони! Отец, вернись в чат {ADMIN_USERNAME}"
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


async def handle_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех сообщений в чате для ответов Клифа"""
    try:
        if update.effective_user.is_bot:
            return

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
        entry_points=[CommandHandler("admin", admin_command)],
        states={
            ADMIN_PANEL: [
                CallbackQueryHandler(admin_button_handler),
            ],
            SWAP_ROLES_FIRST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               handle_swap_roles_first),
            ],
            SWAP_ROLES_SECOND: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               handle_swap_roles_second),
            ],
            FORCE_CHANGE_ROLE_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               handle_select_role_for_status),
            ],
            FORCE_CHANGE_ROLE_STATUS: [
                CallbackQueryHandler(admin_button_handler),
            ],
            ADD_ROLE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_role_name),
            ],
            ADD_ROLE_REGION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               add_role_region),
            ],
            ADD_ROLE_CONFIRM: [
                CallbackQueryHandler(admin_button_handler),
            ],
            DELETE_ROLE_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               delete_role_select),
            ],
            CONFIRM_DELETE_ROLE: [
                CallbackQueryHandler(admin_button_handler),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🔙 Назад в меню$"), back_to_menu),
        ],
        allow_reentry=True,
        per_user=True,
    )


# ===== ЗАПУСК БОТА =====
def main():
    try:
        logger.info("🟢 Запуск бота...")
        telegram_app = Application.builder().token(BOT_TOKEN).build()

        # Фоновая задача для проверки броней
        telegram_app.job_queue.run_repeating(check_expired_bookings,
                                             interval=600,
                                             first=10)

        # 1. Основные команды
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("help", show_help))
        telegram_app.add_handler(
            CommandHandler("cancel_booking", cancel_booking))

        # 2. Обработчики кнопок
        telegram_app.add_handler(
            MessageHandler(filters.Regex(r"⋄┋ⲡⲣⲁⲃυⲗⲁ┋⋄"), show_rules))
        telegram_app.add_handler(
            MessageHandler(filters.Regex(r"⋄┋ⲣⲟⲗυ┋⋄"), show_roles))
        telegram_app.add_handler(
            MessageHandler(filters.Regex(r"⋄┋ⲣⲉⲯυⲙ ⲡⲣυⲉⲙⲁ ⳅⲁяⲃⲟⲕ┋⋄"),
                           show_regime))
        telegram_app.add_handler(
            MessageHandler(filters.Regex(r"⋄┋ⲡⲟⲙⲟⳃь┋⋄"), show_help))
        telegram_app.add_handler(
            MessageHandler(filters.Regex(r"⋄┋ⲏⲁⲱ ⲦⲓⲕⲦⲟⲕ┋⋄"), show_tiktok))

        # 3. Диалоговые обработчики (важен порядок!)
        telegram_app.add_handler(
            setup_admin_conversation())  # Должен быть перед role_selection
        telegram_app.add_handler(setup_role_selection_conversation())

        # 4. Обработчики участников
        telegram_app.add_handler(ChatMemberHandler(handle_participant_update))
        telegram_app.add_handler(
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,
                           handle_participant_update))
        telegram_app.add_handler(
            MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER,
                           handle_participant_update))

        # 5. Обработчик ответов (должен быть последним)
        telegram_app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
                handle_answers,
            ))

        logger.info("🟢 Бот запущен")
        telegram_app.run_polling()
    except Exception as e:
        logger.critical(f"🔴 Критическая ошибка: {e}")
        raise


if __name__ == '__main__':
    keep_alive()  # Запускаем keep_alive для поддержания работы бота
    main()
