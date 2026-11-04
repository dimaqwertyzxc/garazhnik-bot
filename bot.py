import telebot
from telebot import types

# ВСТАВЬ СЮДА СВОЙ ТОКЕН
bot = telebot.TeleBot("9287903988:AAFgxZZVwAQzkqu81J8pRCdQCxbMz_9-jTo")

# ТВОЙ ГЛАВНЫЙ ID (узнать у @userinfobot)
SUPER_ADMIN_ID = 8290888308

admins = {SUPER_ADMIN_ID}
users_db = {}
active_events = {}


def is_admin(user_id):
    return user_id in admins


@bot.message_handler(commands=['start'])
def start_private(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, "Напиши свое имя для регистрации.")
        bot.register_next_step_handler(message, save_name)
    else:
        bot.send_message(message.chat.id, "Бот-казначей запущен.")


def save_name(message):
    users_db[message.from_user.id] = message.text
    bot.send_message(message.chat.id, f"Имя {message.text} сохранено.")


@bot.message_handler(commands=['add_admin'])
def add_admin(message):
    if message.from_user.id != SUPER_ADMIN_ID: return
    if message.reply_to_message:
        admins.add(message.reply_to_message.from_user.id)
        bot.reply_to(message, f"Пользователь {message.reply_to_message.from_user.id} теперь админ.")
    else:
        bot.reply_to(message, "Ответь на сообщение пользователя, чтобы дать права.")


@bot.message_handler(commands=['remove_admin'])
def remove_admin(message):
    if message.from_user.id != SUPER_ADMIN_ID: return
    if message.reply_to_message:
        admins.discard(message.reply_to_message.from_user.id)
        bot.reply_to(message, "Права отозваны.")
    else:
        bot.reply_to(message, "Ответь на сообщение пользователя, чтобы забрать права.")


# --- ОТПРАВКА СООБЩЕНИЙ ---
def send_event_message(chat_id, event_key):
    event = active_events[chat_id][event_key]
    text = f"**{event['title']}**\n\n"

    if 'details' in event:
        text += f"{event['details']}\n\n"

    if event['type'] in ['hockey', 'kopilka']:
        text += f"Сумма: **{event['price']} руб.**\n"

    if event['type'] in ['kopilka', 'hockey']:
        text += f"Перевод: `{event['requisites']}`\nЧек: `{event['check_to']}`\n"

    text += "\n**СПИСОК:**\n"
    idx = 1
    if event['type'] in ['list', 'kopilka']:
        for uid in event['members']:
            name = users_db.get(uid, "Неизвестный")
            if event['type'] == 'kopilka':
                status = " [✅]" if event['members'][uid]['paid'] == 'confirmed' else " [⏳]" if event['members'][uid][
                                                                                                   'paid'] == 'pending' else ""
                text += f"{idx}. {name}{status}\n"
            else:
                text += f"{idx}. {name}\n"
            idx += 1
    elif event['type'] == 'hockey':
        for uid, data in event['members'].items():
            name = users_db.get(uid, "Неизвестный")
            status = " [✅]" if data['paid'] == 'confirmed' else " [⏳]" if data['paid'] == 'pending' else ""
            text += f"{idx}. {name}{status}\n"
            idx += 1
            for friend in data['friends']:
                text += f"   {idx}. {name} (друг)\n"
                idx += 1

    markup = types.InlineKeyboardMarkup()
    if event['type'] == 'list':
        markup.add(types.InlineKeyboardButton("Вписаться", callback_data=f"join_{event_key}"))
        markup.add(types.InlineKeyboardButton("Выписаться", callback_data=f"leave_{event_key}"))
    if event['type'] == 'hockey':
        markup.add(types.InlineKeyboardButton("Вписаться", callback_data=f"join_{event_key}"))
        markup.add(types.InlineKeyboardButton("Выписаться", callback_data=f"leave_{event_key}"))
        markup.add(types.InlineKeyboardButton("Добавить друга", callback_data=f"addfriend_{event_key}"))
        markup.add(types.InlineKeyboardButton("Убрать друга", callback_data=f"removefriend_{event_key}"))
        markup.add(types.InlineKeyboardButton("Я оплатил", callback_data=f"pay_{event_key}"))
    if event['type'] == 'kopilka':
        markup.add(types.InlineKeyboardButton("Я сдал", callback_data=f"pay_{event_key}"))

    try:
        bot.edit_message_text(chat_id=chat_id, message_id=event['message_id'], text=text, reply_markup=markup,
                              parse_mode='Markdown')
    except Exception:
        pass


# --- КОМАНДЫ ---

@bot.message_handler(commands=['kamorka'])
def create_kamorka(message):
    if not is_admin(message.from_user.id): return
    try:
        args = message.text.replace('/kamorka', '').strip().split(',')
        place = args[0].strip()
        time_ev = args[1].strip()
    except IndexError:
        return bot.reply_to(message, "Формат: `/kamorka Место, Время`\nПример: `/kamorka Синий пандус, 19:00`",
                            parse_mode='Markdown')

    chat_id = message.chat.id
    if chat_id not in active_events: active_events[chat_id] = {}

    active_events[chat_id]['kamorka'] = {'type': 'list', 'title': "Сбор", 'details': f"Где: {place}\nКогда: {time_ev}",
                                         'members': {}, 'message_id': None}
    msg = bot.send_message(chat_id, "Создаю...")
    active_events[chat_id]['kamorka']['message_id'] = msg.message_id
    send_event_message(chat_id, 'kamorka')


@bot.message_handler(commands=['kopilka'])
def create_kopilka(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.replace('/kopilka', '').strip().split(',')
        if len(parts) < 5: raise IndexError
        month = parts[0].strip().capitalize()
        price = parts[1].strip()
        deadline = parts[2].strip()
        requisites = parts[3].strip()
        check_to = parts[4].strip()
    except IndexError:
        return bot.reply_to(message,
                            "Формат: `/kopilka Месяц, Сумма, Дедлайн, Реквизиты, Кому чек`\nПример: `/kopilka Ноябрь, 500, 30.11, +79991234567, @admin`",
                            parse_mode='Markdown')

    chat_id = message.chat.id
    if chat_id not in active_events: active_events[chat_id] = {}

    details = f"Копилка за {month}\nСдать до {deadline}"
    active_events[chat_id]['kopilka'] = {'type': 'kopilka', 'title': "Копилка", 'details': details, 'price': price,
                                         'requisites': requisites, 'check_to': check_to, 'members': {},
                                         'message_id': None}
    msg = bot.send_message(chat_id, "Создаю...")
    active_events[chat_id]['kopilka']['message_id'] = msg.message_id
    send_event_message(chat_id, 'kopilka')


@bot.message_handler(commands=['hockey'])
def create_hockey(message):
    if not is_admin(message.from_user.id): return
    try:
        args = message.text.replace('/hockey', '').strip().split(',')
        if len(args) < 5: raise IndexError
        opponent = args[0].strip()
        time_ev = args[1].strip()
        price = args[2].strip()
        requisites = args[3].strip()
        check_to = args[4].strip()
    except IndexError:
        return bot.reply_to(message,
                            "Формат: `/hockey Соперник, Время, Цена, Реквизиты, Кому чек`\nПример: `/hockey Динамо, 15.11_19:30, 1000, +79991234567, @admin`",
                            parse_mode='Markdown')

    chat_id = message.chat.id
    if chat_id not in active_events: active_events[chat_id] = {}

    details = f"Матч: Спартак - {opponent}\nВремя: {time_ev}"
    active_events[chat_id]['hockey'] = {'type': 'hockey', 'title': "Хоккей", 'details': details, 'price': price,
                                        'requisites': requisites, 'check_to': check_to, 'members': {},
                                        'message_id': None}
    msg = bot.send_message(chat_id, "Создаю...")
    active_events[chat_id]['hockey']['message_id'] = msg.message_id
    send_event_message(chat_id, 'hockey')


# --- КНОПКИ ---
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    if data.startswith("confirm:"):
        if call.from_user.id != SUPER_ADMIN_ID:
            return bot.answer_callback_query(call.id, "Ты не админ.")

        _, ev_key, uid, target_chat_id = data.split(':')
        uid = int(uid)
        target_chat_id = int(target_chat_id)

        if target_chat_id in active_events and ev_key in active_events[target_chat_id]:
            if uid in active_events[target_chat_id][ev_key]['members']:
                active_events[target_chat_id][ev_key]['members'][uid]['paid'] = 'confirmed'
                send_event_message(target_chat_id, ev_key)
                bot.answer_callback_query(call.id, "Оплата подтверждена.")
            else:
                bot.answer_callback_query(call.id, "Пользователь не найден.")
        else:
            bot.answer_callback_query(call.id, "Сбор не найден.")
        return

    parts = data.split('_')
    action = parts[0]
    event_key = parts[1]

    if chat_id not in active_events or event_key not in active_events[chat_id]:
        return bot.answer_callback_query(call.id, "Событие не найдено.")

    event = active_events[chat_id][event_key]

    if user_id not in users_db:
        return bot.answer_callback_query(call.id, "Сначала напиши /start в личку!", show_alert=True)

    if action == "join":
        if event['type'] == 'hockey':
            if user_id not in event['members']:
                event['members'][user_id] = {'friends': [], 'paid': 'no'}
        else:
            if user_id not in event['members']:
                event['members'][user_id] = {'paid': 'no'}
        bot.answer_callback_query(call.id, "Ты в списке.")

    elif action == "leave":
        if user_id in event['members']:
            del event['members'][user_id]
        bot.answer_callback_query(call.id, "Ты выписан.")

    elif action == "addfriend":
        if user_id in event['members']:
            event['members'][user_id]['friends'].append(True)
            bot.answer_callback_query(call.id, "Друг добавлен.")
        else:
            bot.answer_callback_query(call.id, "Сначала впишись.")

    elif action == "removefriend":
        if user_id in event['members'] and event['members'][user_id]['friends']:
            event['members'][user_id]['friends'].pop()
            bot.answer_callback_query(call.id, "Последний друг убран.")
        else:
            bot.answer_callback_query(call.id, "Нет друзей для удаления.")

    elif action == "pay":
        # ЖЕЛЕЗНОЕ ПРАВИЛО ДЛЯ ХОККЕЯ
        if event['type'] == 'hockey':
            if user_id not in event['members']:
                return bot.answer_callback_query(call.id, "Сначала нажми 'Вписаться'!", show_alert=True)

        # Для копилки (если вдруг не в списке, добавляем автоматически)
        if event['type'] == 'kopilka':
            if user_id not in event['members']:
                event['members'][user_id] = {'paid': 'no'}

        event['members'][user_id]['paid'] = 'pending'
        bot.answer_callback_query(call.id, "Отправлено админу.")
        send_event_message(chat_id, event_key)

        username = users_db.get(user_id, "Неизвестный")
        confirm_data = f"confirm:{event_key}:{user_id}:{chat_id}"

        bot.send_message(SUPER_ADMIN_ID, f"Пользователь {username} нажал кнопку оплаты в сборе '{event['title']}'.")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Подтвердить", callback_data=confirm_data))
        bot.send_message(SUPER_ADMIN_ID, f"Подтвердить оплату для {username}?", reply_markup=markup)

    send_event_message(chat_id, event_key)


print("Бот запущен.")
bot.infinity_polling()