from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from telebot import types, TeleBot, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import json
import os
import random


###Создаем и заполняем базы данных###

load_dotenv()
Base = declarative_base()


class Dictionary(Base):
    __tablename__ = 'dictionary'
    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String, nullable=False)
    translation = Column(String, nullable=False)
    complexity = Column(String, nullable=False)

    def __str__(self):
        return f'Dictionary: {self.id}, {self.word}, {self.translation}, {self.person_id}, {self.complexity}'


class Person_action(Base):
    __tablename__ = 'person_action'
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey('person.id'), nullable=False)  # <-- ForeignKey!
    word = Column(String, nullable=False)
    translation = Column(String, nullable=False)
    complexity = Column(String, nullable=False)
    action = Column(String, nullable=False)  # 'add' или 'dell'
    person = relationship('Person', back_populates='person_action')

    def __str__(self):
        return f'Dictionary: {self.id}, {self.person_id}, {self.word}, {self.translation}, {self.complexity}, {self.action}'


class Person(Base):
    __tablename__ = 'person'
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, unique=True)
    person_action = relationship('Person_action', back_populates='person')

    def __str__(self):
        return f'Dictionary: {self.id}, {self.telegram_id}'


DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def create_tables(engine):
    # Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

def drop_tables(engine):
    Base.metadata.drop_all(engine)

def load_data():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = Session()
    with open('large_words_dataset.json', 'r', encoding='utf-8') as fd:
        data = json.load(fd)
    for record in data:
        session.add(Dictionary(word=record.get('word'), translation=record.get('translation'), complexity=record.get('complexity')))
    session.commit()
    session.close()
    print("Данные успешно загружены.")


engine = create_engine(DSN)
drop_tables(engine)
create_tables(engine)
Session = sessionmaker(bind=engine)
session = Session()
load_data()
print('Телеграм бот запущен.')


###Создаем телеграм бота###


state_storage = StateMemoryStorage()
TOKEN_BOT = os.getenv('TOKEN_BOT')
bot = TeleBot(TOKEN_BOT, state_storage=state_storage)
os.getenv('DB_USER')
known_users = []
user_mode = {}  # {telegram_id: 10 | 50 | 100}
user_progress = {}  # {telegram_id: {'total': 0, 'correct': 0}}
userStep = {}
buttons = []
user_level = {}  # {telegram_id: 'easy' | 'normal' | 'hard'}
user_answered_correctly = {}  # {telegram_id: bool}


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'

class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()


def show_hint(*lines):
    return '\n'.join(lines)

def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_btn = types.KeyboardButton('▶️ Начать')
    level_btn = types.KeyboardButton('⚙️ Уровень')
    mode_btn = types.KeyboardButton('🎯 Режим')
    add_btn = types.KeyboardButton(Command.ADD_WORD)
    del_btn = types.KeyboardButton(Command.DELETE_WORD)
    markup.add(start_btn, level_btn)
    markup.add(mode_btn, add_btn, del_btn)
    bot.send_message(
        message.chat.id,
        "📚 Главное меню:\nВыберите опцию для продолжения.",
        reply_markup=markup
    )

###ХЭНДЛЕРЫ###

@bot.message_handler(func=lambda message: message.text == '🎯 Режим')
def choose_mode(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    btn10 = types.KeyboardButton('10 слов')
    btn50 = types.KeyboardButton('50 слов')
    btn100 = types.KeyboardButton('100 слов')
    markup.add(btn10, btn50, btn100)
    bot.send_message(message.chat.id, "Выбери количество слов в сессии:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ['10 слов', '50 слов', '100 слов'])
def set_mode(message):
    count = int(message.text.split()[0])
    user_mode[message.chat.id] = count
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_btn = types.KeyboardButton('▶️ Начать')
    level_btn = types.KeyboardButton('⚙️ Уровень')
    mode_btn = types.KeyboardButton('🎯 Режим')
    markup.add(start_btn, level_btn)
    markup.add(mode_btn)
    bot.send_message(
        message.chat.id,
        f"✅ Установлен режим: {count} слов.",
    )
    show_main_menu(message)

@bot.message_handler(commands=['level'])
def set_difficulty(message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    btn_easy = types.KeyboardButton('easy')
    btn_normal = types.KeyboardButton('normal')
    btn_hard = types.KeyboardButton('hard')
    markup.add(btn_easy, btn_normal, btn_hard)
    bot.send_message(message.chat.id, "Выбери уровень сложности слов:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ['easy', 'normal', 'hard'])
def save_level(message):
    user_level[message.chat.id] = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_btn = types.KeyboardButton('▶️ Начать')
    level_btn = types.KeyboardButton('⚙️ Уровень')
    mode_btn = types.KeyboardButton('🎯 Режим')
    markup.add(start_btn, level_btn)
    markup.add(mode_btn)
    bot.send_message(
        message.chat.id,
        f"✅ Выбран уровень сложности: {message.text}.",
    )
    show_main_menu(message)

@bot.message_handler(commands=['start'])
def start_handler(message):
    session = Session()
    # Проверка: если пользователь уже зарегистрирован, сразу даём меню
    existing_user = session.query(Person).filter_by(telegram_id=message.chat.id).first()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    if not existing_user:
        login_btn = types.KeyboardButton('🔐 Log in')
        markup.add(login_btn)
        bot.send_message(
            message.chat.id,
            "Добро пожаловать!\nЧтобы начать, нажмите 🔐 Log in.",
            reply_markup=markup
        )
    else:
        show_main_menu(message)
    session.close()

@bot.message_handler(func=lambda message: message.text == '🔐 Log in')
def login_user(message):
    session = Session()
    # Проверяем, не зарегистрирован ли уже
    existing = session.query(Person).filter_by(telegram_id=message.chat.id).first()
    if existing:
        bot.send_message(message.chat.id, "✅ Вы уже зарегистрированы.")
        session.close()
        show_main_menu(message)
        return
    # Регистрируем
    new_user = Person(telegram_id=message.chat.id)
    session.add(new_user)
    session.commit()
    session.close()
    bot.send_message(message.chat.id, "✅ Регистрация прошла успешно.")
    show_main_menu(message)

@bot.message_handler(func=lambda message: message.text == '▶️ Начать')
def start_learning(message):
    create_cards(message)

@bot.message_handler(func=lambda message: message.text == '⚙️ Уровень')
def level_button_handler(message):
    set_difficulty(message)

@bot.message_handler(func=lambda message: message.text == 'cards')
def create_cards(message):
    cid = message.chat.id
    if cid not in known_users:
        known_users.append(cid)
        userStep[cid] = 0
        bot.send_message(cid, f"Hello, {cid}, let study English...")
    markup = types.ReplyKeyboardMarkup(row_width=2)
    user_answered_correctly[message.chat.id] = False
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DSN)
    Session = sessionmaker(bind=engine)
    session = Session()
    existing_user = session.query(Person).filter_by(telegram_id=message.chat.id).first()
    global buttons
    buttons = []
    if message.chat.id not in user_level:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        level_btn = types.KeyboardButton('⚙️ Уровень')
        markup.add(level_btn)
        bot.send_message(cid, "Сначала выбери уровень сложности:", reply_markup=markup)
        return
    total = user_mode.get(cid, 10)
    if cid not in user_progress:
        user_progress[cid] = {'total': 0, 'correct': 0}
    # если пользователь уже прошёл нужное количество слов — конец
    if user_progress[cid]['total'] >= total:
        correct = user_progress[cid]['correct']
        user_progress[cid] = {'total': 0, 'correct': 0}  # сброс
        # Главное меню с возможностью добавления/удаления
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        start_btn = types.KeyboardButton('▶️ Начать')
        level_btn = types.KeyboardButton('⚙️ Уровень')
        mode_btn = types.KeyboardButton('🎯 Режим')
        add_btn = types.KeyboardButton(Command.ADD_WORD)
        del_btn = types.KeyboardButton(Command.DELETE_WORD)
        markup.add(start_btn, level_btn)
        markup.add(mode_btn, add_btn, del_btn)
        bot.send_message(
            cid,
            f"🏁 Сессия завершена!\n✅ Правильных ответов: {correct} из {total}",
            reply_markup=markup
        )
        return

    query = text("""
        SELECT word, translation FROM (
            SELECT word, translation FROM dictionary WHERE complexity = :complexity
            UNION
            SELECT word, translation FROM person_action
            WHERE person_id = :person_id AND action = 'add' AND complexity = :complexity
        ) AS combined_words
        ORDER BY RANDOM()
        LIMIT 4
    """)
    person = session.query(Person).filter_by(telegram_id=cid).first()
    result = session.execute(query, {'person_id': person.id, 'complexity': user_level[cid]}).fetchall()
    correct_card = random.choice(result)

    buttons = [types.KeyboardButton(row.translation) for row in result]
    random.shuffle(buttons)
    buttons.append(types.KeyboardButton(Command.NEXT))
    markup.add(*buttons)
    greeting = f"Выбери перевод слова:\n🇷🇺 {correct_card.word}"
    bot.send_message(cid, greeting, reply_markup=markup)
    # Сохраняем данные в состоянии для проверки ответа
    bot.set_state(message.from_user.id, MyStates.target_word, cid)
    with bot.retrieve_data(message.from_user.id, cid) as data:
        data['target_word'] = correct_card.translation
        data['translate_word'] = correct_card.word
        data['other_translations'] = [row.translation for row in result if row.translation != correct_card.translation]
    session.close()

@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    user_id = message.chat.id
    if not user_answered_correctly.get(user_id, False):
        bot.send_message(user_id, "❗ Сначала ответьте правильно, прежде чем переходить к следующему слову.")
        return
    create_cards(message)

@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def add_word(message):
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DSN)
    Session = sessionmaker(bind=engine)
    session = Session()
    bot.send_message(message.chat.id, "Введите слово, которое хотите удалить."
                                      " Пример: снег")
    bot.register_next_step_handler(message, dell_word)
def dell_word(message):
    word_input = message.text.strip().lower()
    # Получаем id пользователя
    id_to_add = session.query(Person.id).filter(Person.telegram_id == int(message.chat.id)).one()
    p_id = id_to_add[0]
    # ПРОВЕРЯЕМ, СУЩЕСТВУЕТ ЛИ ВООБЩЕ В СЛОВАРЕ СЛОВО, КОТОРОЕ ХОЧЕТ УДАЛИТЬ ПОЛЬЗОВАТЕЛЬ, ПОСЛЕ - ДОБАВЛЯЕМ ЕГО В PERSON_ACTION С ПОМЕТКОЙ DELL
    word_entry = session.query(Dictionary).filter(Dictionary.word.ilike(word_input)).first()
    if word_entry:
        if word_entry:
            # Проверка, удалял ли уже пользователь это слово
            already_deleted = session.query(Person_action).filter_by(
                person_id=p_id,
                word=word_entry.word,
                translation=word_entry.translation,
                complexity=word_entry.complexity,
                action='dell'
            ).first()
            if already_deleted:
                bot.send_message(
                    message.chat.id,
                    f"⚠️ Слово `{word_entry.word}` уже было удалено вами ранее.",
                    parse_mode="Markdown"
                )
                session.close()
                return
        new_pair = Person_action(
            person_id=p_id,
            word=word_entry.word,
            translation=word_entry.translation,
            complexity=word_entry.complexity,
            action='dell'
        )
        session.add(new_pair)
        session.commit()
        bot.send_message(
            message.chat.id,
            f"❌ Слово {word_entry.word} ({word_entry.translation}) удалено из словаря."
        )
        print(f'{new_pair} добавлено в базу как удалённое слово.')
    else:
        bot.send_message(message.chat.id, "⚠️ Такое слово не найдено в словаре.")


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DSN)
    Session = sessionmaker(bind=engine)
    session = Session()
    bot.send_message(message.chat.id, "Введите слово, которое хотите добавить согласно конструкции "
                                      "(слово перевод сложность(easy, hard)). "
                                      "Пример: последовательность sequence hard")
    bot.register_next_step_handler(message, add_word_to_DB)
def add_word_to_DB(message):

    parts = message.text.strip().split()
    if len(parts) != 3 or parts[2].lower() not in ['easy', 'normal', 'hard']:
        bot.send_message(
            message.chat.id,
            "⚠️ Неверный формат. Пожалуйста, введите слово в формате:\n"
            "`слово перевод сложность`\nПример: последовательность sequence hard",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(message, add_word_to_DB)
        return

    word, translation, complexity = parts
    session = Session()
    person = session.query(Person).filter_by(telegram_id=message.chat.id).first()
    if not person:
        bot.send_message(message.chat.id, "❗ Сначала пройдите регистрацию с помощью /start")
        session.close()
        return
    # Проверка, добавлял ли пользователь это слово ранее
    already_added = session.query(Person_action).filter_by(
        person_id=person.id,
        word=word,
        translation=translation,
        complexity=complexity.lower(),
        action='add'
    ).first()
    if already_added:
        bot.send_message(
            message.chat.id,
            f"⚠️ Слово `{word}` – `{translation}` уже добавлено вами ранее.",
            parse_mode="Markdown"
        )
        session.close()
        return
    new_pair = Person_action(
        person_id=person.id,
        word=word,
        translation=translation,
        complexity=complexity.lower(),
        action='add'
    )
    session.add(new_pair)
    session.commit()
    session.close()

    bot.send_message(message.chat.id, f"✅ Новое слово `{word}` – `{translation}` добавлено в словарь.", parse_mode="Markdown")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    new_buttons = []

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            # Правильный ответ — сбрасываем флаг ошибки
            data['made_mistake'] = False
            user_answered_correctly[message.chat.id] = True
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]
            next_btn = types.KeyboardButton(Command.NEXT)
            new_buttons.append(next_btn)
            hint = show_hint(*hint_text)
            user_progress[message.chat.id]['correct'] += 1
            user_progress[message.chat.id]['total'] += 1
        else:
            # Неправильный ответ — учитываем ошибку только один раз
            if not data.get('made_mistake', False):
                data['made_mistake'] = True
                user_progress[message.chat.id]['correct'] -= 1
            hint = show_hint(
                "Допущена ошибка!",
                f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}"
            )
    markup.add(*new_buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)

bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(skip_pending=True)
