import logging, requests, io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler, Filters
from typing import List
from config import TELEGRAM_BOT_TOKEN, API_TOKEN, API_URL

# Настройка журнала
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Создаем клавиатуру для выбора способа поиска
def create_search_keyboard():
    keyboard = [
        [InlineKeyboardButton("Искать по названию", callback_data="search_by_title")],
        [InlineKeyboardButton("Искать по идентификатору КиноПоиска", callback_data="search_by_kinopoisk_id")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Функция для обработки выбора способа поиска
def search_option(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == "search_by_title":
        context.user_data['search_option'] = 'title'
        query.message.reply_text("Введите название фильма, который вы ищете:")
    elif query.data == "search_by_kinopoisk_id":
        context.user_data['search_option'] = 'kinopoisk_id'
        query.message.reply_text("Введите идентификатор КиноПоиска фильма, который вы ищете:")

# Обработчик для кнопки "Поиск по названию"
def search_by_title_button(update: Update, context: CallbackContext):
    context.user_data['search_option'] = 'title'
    update.message.reply_text("Введите название фильма, который вы ищете:")

# Обработчик для кнопки "Поиск по ид кинопоиска"
def search_by_kinopoisk_id_button(update: Update, context: CallbackContext):
    context.user_data['search_option'] = 'kinopoisk_id'
    update.message.reply_text("Введите идентификатор КиноПоиска фильма, который вы ищете:")

# Обновите функцию start для отправки как кнопок ReplyKeyboardMarkup, так и кнопок InlineKeyboardButton
def start(update: Update, context: CallbackContext):
    button1 = KeyboardButton('Поиск по названию(Title)')
    button2 = KeyboardButton('Поиск по ид кинопоиска(ID)')

    keyboard = ReplyKeyboardMarkup([[button1, button2]], resize_keyboard=True, one_time_keyboard=True)

    text = "Привет! Этот бот поможет вам найти информацию о фильмах. Выберите способ поиска:"
    update.message.reply_text(text, reply_markup=keyboard)
    update.message.reply_text("Или выберите способ поиска с помощью кнопок ниже:", reply_markup=create_search_keyboard())

# Глобальные переменные для хранения результатов поиска
search_results = []
current_index = 0

# Функция для форматирования информации о фильме
def format_movie(movie_info):
    return f"Название: {movie_info['title_ru']}\nГод выпуска: {movie_info['year']}"

# Функция для выполнения поиска по названию
def search_movie(query, update, context):
    global search_results
    global current_index

    params = {
        'title': query,
        'token': API_TOKEN
    }
    response = requests.get(API_URL, params=params)
    search_results = response.json()
    search_results = remove_duplicates(search_results)

    if search_results:
        current_index = 0
        send_movie_info(update, context, search_results[current_index], 'title')
    else:
        update.message.reply_text("Фильм не найден.")

# Функция для обработки текстового сообщения с запросом
def search_by_text(update: Update, context: CallbackContext):
    query = update.message.text
    search_option = context.user_data.get('search_option')
    if query == 'Поиск по названию(Title)':
        search_by_title_button(update, context)
    elif query == 'Поиск по ид кинопоиска(ID)':
        search_by_kinopoisk_id_button(update, context)
    else:
        if search_option == 'title':
            response = search_movie(query, update, context)
            if response is not None:
                keyboard = create_pagination_keyboard()
                context.bot.send_message(chat_id=update.effective_chat.id, text=response, reply_markup=keyboard)
        else:
            if query.isdigit():  # Проверяем, является ли введенный текст числом (идентификатор КиноПоиска)
                response = search_by_kinopoisk_id(query, update, context)
                if response is not None:
                    context.bot.send_message(chat_id=update.effective_chat.id, text=response)
            else:
                context.bot.send_message(chat_id=update.effective_chat.id, text="Активирован режим поиска по идентификатору КиноПоиска. Введите идентификатор КиноПоиска фильма.")

# Функция для отправки изображения с подписью
def send_movie_info(update, context, movie_info, ud):
    poster_url = movie_info.get('poster')
    title = movie_info.get('title_ru')
    year = movie_info.get('year')
    if poster_url:
        # Скачиваем изображение по URL
        response = requests.get(poster_url)

        if response.status_code == 200:
            # Отправляем изображение как фото
            if ud == 'title':
                context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(io.BytesIO(response.content)), caption=f"Название: {title}\nГод выпуска: {year}", reply_markup=create_pagination_keyboard())
            else:
                context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(io.BytesIO(response.content)), caption=f"Название: {title}\nГод выпуска: {year}")
        else:
            update.message.reply_text("Не удалось загрузить постер фильма.")
    else:
        update.message.reply_text("Постер фильма недоступен.")

# Обновите функцию search_by_kinopoisk_id
def search_by_kinopoisk_id(kinopoisk_id, update: Update, context: CallbackContext):
    params = {
        'id_kp': kinopoisk_id,
        'token': API_TOKEN
    }
    response = requests.get(API_URL, params=params)
    data = response.json()
    print(data)
    if data:
        if len(data) > 0:
            movie_info = data[0]
            send_movie_info(update, context, movie_info, 'id')
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="Фильм не найден.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Фильм не найден.")

# Функции для пролистывания результатов
def next_movie(update: Update, context: CallbackContext):
    global current_index
    current_index += 1
    if current_index < len(search_results):
        send_movie_info(update, context, search_results[current_index], 'title')
    else:
        current_index = len(search_results) - 1
        message_text = "Больше фильмов нет."
        context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=create_pagination_keyboard())

def prev_movie(update: Update, context: CallbackContext):
    global current_index
    current_index -= 1
    if current_index >= 0:
        send_movie_info(update, context, search_results[current_index], 'title')
    else:
        current_index = 0
        message_text = "Это первый фильм."
        context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=create_pagination_keyboard())

def current_movie(update: Update, context: CallbackContext):
    if current_index < len(search_results):
        send_movie_info(update, context, search_results[current_index], 'title')
    else:
        message_text = "Нет данных о текущем фильме."
        context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=create_pagination_keyboard())

# В функции create_pagination_keyboard добавим кнопку "current"
def create_pagination_keyboard():
    buttons = []
    if len(search_results) > 1:
        if current_index > 0:
            buttons.append(InlineKeyboardButton("Предыдущий", callback_data="prev"))
        buttons.append(InlineKeyboardButton(f"{current_index + 1} из {len(search_results)}", callback_data="current"))
        if current_index < len(search_results) - 1:
            buttons.append(InlineKeyboardButton("Следующий", callback_data="next"))

    return InlineKeyboardMarkup(build_menu(buttons, n_cols=1))

# Функция для построения меню кнопок
def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

def remove_duplicates(movies):
    unique_movies = []
    seen_kinopoisk_ids = set()

    for movie in movies:
        kinopoisk_id = movie.get('kinopoisk_id')
        if kinopoisk_id not in seen_kinopoisk_ids:
            unique_movies.append(movie)
            seen_kinopoisk_ids.add(kinopoisk_id)

    return unique_movies

def main():
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(search_option, pattern='^search_by_'))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, search_by_text))
    dp.add_handler(MessageHandler(Filters.regex(r'^\d+$'), search_by_kinopoisk_id))
    dp.add_handler(CallbackQueryHandler(prev_movie, pattern='^prev'))
    dp.add_handler(CallbackQueryHandler(next_movie, pattern='^next'))
    dp.add_handler(CallbackQueryHandler(current_movie, pattern='^current'))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
