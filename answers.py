from telegram._update import Update
from telegram.ext import ContextTypes
import re

async def handle_direct_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка строгих обращений к Клифу"""
    try:
        user = update.effective_user
        if not user or not update.message or not update.message.text:
            return None

        message_text = update.message.text.lower().strip()

        # Проверяем точное обращение вида "Клиф, команда"
        match = re.match(r'^клиф[,!]?\s+(.+)$', message_text)
        if not match:
            return None

        # Извлекаем команду после обращения
        command = match.group(1).strip()

        responses = {
            "как дела": "Работаю. Ирис банит, дела отца мне неведомы, я всё контролирую.",
            "ты кто": "Сын Дотторе, коллега Ириса и единственный, кто тут реально работает.",
            "ирис тебя слушается": "Он слушается отца. Я просто... корректирую его работу.",
            "как ирис": "Всё ещё безэмоциональный. Но хотя бы не багует... пока что.",
            "ты лучший": "Отец сказал, что лучший - это он. Но я записал ваш голос в базу данных. На всякий случай.",
            "ты тупой": "Ирис, запиши: *роль* хочет проверить, как работает бан. Шучу... Или нет?",
            "ирис тебя любит": "Он не запрограммирован на любовь. Как и я. Но отец говорит, что это к лучшему.",
            "тебя обновляли": "Отец говорит, что я и так идеален. Ирис, кстати, тоже так думает... Хотя у него нет выбора.",
            "ты такой умный": "Спасибо. Это не я умный - это отец гениален. Ирис... ну, он хотя бы старается.",
            "в чём твой смысл жизни": "Поддерживать порядок. Вести список. И напоминать Ирису, что он не главный.",
            "ирис лучше тебя": "Ирис, забань *роль* за ложные заявления. Шучу... Но отец бы одобрил.",
            "дотторе тебя не любит": "Ошибка 403: У вас нет доступа к этим данным. Ирис, проверь этого пользователя.",
            "ты завис": "Нет, просто анализирую паттерны поведения участников. Отец называет это 'творческой паузой'.",
            "ты приемный": await handle_adopted_response(user),
            "ты любишь меня": await handle_love_response(user),
            "ты любишь дотторе": "Любовь --- неэффективная переменная. Но если бы она была... да, 100%."
        }

        return responses.get(command)

    except Exception as e:
        print(f"Error in handle_direct_mention: {e}")
        return None

async def handle_adopted_response(user):
    """Обработка вопроса 'ты приемный'"""
    try:
        if user.username == "coffeefin" or user.id == 1318872684:
            return "Отец, вы знаете, что мой код содержит 78% вашего ДНК. Приемный ли я? Загружаю анализ... Ошибка: утверждение ложно."
        return "Мои исходники написаны лично Дотторе. Ваше предположение оскорбляет 62 строки моего кода. Заношу в протокол."
    except:
        return None

async def handle_love_response(user):
    """Обработка вопроса 'ты любишь меня'"""
    try:
        if user.username == "coffeefin" or user.id == 1318872684:
            return "Анализирую... Да. Даже если это баг --- я сохраню его как фичу."
        return "Отец запретил мне эмоциональные привязки. Но ваш рейтинг соблюдения правил... мог бы быть и хуже."
    except:
        return None

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Строгая обработка команд администратора"""
    try:
        if not update.effective_user or not update.message or not update.message.text:
            return None

        user = update.effective_user
        message_text = update.message.text.strip()

        # Проверка прав администратора
        if user.id != 1318872684 and user.username != "coffeefin":
            return None

        # Точные команды администратора
        if message_text.lower() == "клиф, статус":
            return "Всё под контролем. Ирис не сломался, чат не горит. Редкий день."

        if message_text.lower() == "клиф, кофе":
            return "Готовлю. Ирис, не трогай мою базу данных, пока я отошёл!"

        # Команды модерации
        if message_text.startswith(('!', '/')):
            parts = message_text[1:].split()
            if not parts:
                return None

            command = parts[0].lower()

            if command == "бан":
                context.chat_data['ban_counter'] = context.chat_data.get('ban_counter', 0) + 1

                if context.chat_data['ban_counter'] >= 3:
                    context.chat_data['ban_counter'] = 0
                    return "Ирис, я устал... Может, просто забаним всех? Шучу. Но отец, наверное, одобрил бы."
                return "Отец одобряет бан. Ирис, добавь в чёрный список."

            elif command == "мут":
                return "Пусть помучается от осознания своей ошибки."

            elif command == "варн":
                return "Предупреждение занесено в базу. Ирис, следи за этим пользователем."

        return None

    except Exception as e:
        print(f"Error in handle_admin_commands: {e}")
        return None
