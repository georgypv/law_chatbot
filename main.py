import telebot
import core
import json
import config
from telebot import types
bot = telebot.TeleBot(config.token)
doc = core.load_doc('main.docx')
corp = core.preprocess_corpus(doc)

with open('main.json', 'r', encoding='utf-8') as f:
    links_dictionary = json.load(f)

def keyboard_feedback():
    keyboard = types.InlineKeyboardMarkup()
    next_5 = types.InlineKeyboardButton(text='🔍Показать следующие пять ответов', callback_data='next5')
    feedback = types.InlineKeyboardButton(text='📣Оставить отзыв', url='https://t.me/softestingchannel')
    keyboard.add(next_5)
    keyboard.add(feedback)
    return keyboard

def keyboard_feedback2():
    keyboard = types.InlineKeyboardMarkup()
    feedback = types.InlineKeyboardButton(text='📣Оставить отзыв', url='https://t.me/softestingchannel')
    keyboard.add(feedback)
    return keyboard

def keyboard_start_menu():
    keyboard = types.InlineKeyboardMarkup()
    laws_list = types.InlineKeyboardButton(text= '📜Список всех поддерживаемых законов', callback_data='laws_list')
    #ind_law = types.InlineKeyboardButton(text =  '📖Искать в определенном законе', callback_data='ind_law')
    #all_laws = types.InlineKeyboardButton(text = '📚Искать во всех законах', callback_data='all_laws')
    keyboard.add(laws_list)
    #keyboard.add(ind_law)
    #keyboard.add(all_laws)
    return keyboard


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_message = 'этот бот поможет Вам найти нужную информацию из избранных ' + \
                   'юридических документов, которые часто используются в работе ' + \
                   'отдела DPO.\n\n' +  \
                   '📌Напишите запрос в виде вопроса или набора ключевых слов. ' + \
                   'Имейте в виду: чем конкретней и полнее запрос, тем выше точность ответов!\n' + \
                   '📌Запрос должен заканчиваться на знак вопроса ("?")!\n\n' + \
                   'Примеры возможных запросов: \n\n' + \
                   'Что делать, если обнаружена неточность или неполнота в персональных данных?\n\n' + \
                   'Какой срок исполнения обязанностей по соблюдению конфиденциальности информации?\n\n' +\
                   'Источник формирования кредитной истории что это?\n\n' + \
                   'Кредитный отчет что содержит?\n\n' + \
                   'Основания для отказа во внесении сведений в государственный реестр?\n'

    bot.reply_to(message, text = 'Привет👋 ' + message.from_user.first_name + ', ' + help_message, reply_markup = keyboard_start_menu())

@bot.message_handler(commands=['laws'])
def send_laws_list(message):
    bot.reply_to(message, text=config.list_of_laws)

@bot.message_handler(func=lambda message: True)
def echo_all(message):

    if message.text[-1] == '?':
        index_string = core.top_docs_bm25okapi(message.text, corp, 5)
        answer = ''
        for idx in index_string:
            if str(idx) in links_dictionary:
                for item in links_dictionary[str(idx)]:
                    answer += item + '\n'
                answer += doc[idx] + '\n\n'
            else:
                answer += str(idx) + '\n' + doc[idx] + '\n\n'

        bot.reply_to(message, answer, reply_markup=keyboard_feedback())

    else:
        bot.reply_to(message, text='Запрос должен оканчиваться на знак вопроса ("?")')


@bot.callback_query_handler(lambda call: True)
def callback_answer(call):
    if call.data == 'da':
        bot.answer_callback_query(call.id, text='Спасибо за ответ!😃', show_alert=False)

    elif call.data == 'nyet':
        bot.answer_callback_query(call.id, text='Жаль!😔 Мы обязательно сделаем результат лучше!', show_alert=False)

    elif call.data == 'laws_list':
        bot.reply_to(call.message, text=config.list_of_laws)

    elif call.data == 'ind_law':
        bot.answer_callback_query(call.id, text='Пока здесь ничего нет', show_alert=True)

    elif call.data == 'all_laws':
        bot.answer_callback_query(call.id, text='Пока здесь ничего нет', show_alert=True)

    elif call.data == 'next5':

        index_string = core.top_docs_bm25okapi(call.message.text, corp, 10)
        index_string_2 = index_string[5:10]
        answer = ''
        for idx in index_string_2:
            if str(idx) in links_dictionary:
                for item in links_dictionary[str(idx)]:
                    answer += item + '\n'
                answer += doc[idx] + '\n\n'
            else:
                answer += str(idx) + '\n' + doc[idx] + '\n\n'
        bot.reply_to(call.message, text = answer, reply_markup=keyboard_feedback2())

bot.polling()



