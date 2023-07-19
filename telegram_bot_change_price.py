import time
import requests
import configparser
import telebot
from loguru import logger
import traceback
import json


logger.add('log.log')


config = configparser.ConfigParser()
config.read('settings.ini', encoding='utf-8')


bot = telebot.TeleBot(token=config.get('SETTINGS', 'bot_token'))


def get_prices():
    headers = {
        'Authorization': config.get('SETTINGS', 'wb_token')
    }
    url = 'https://suppliers-api.wildberries.ru/public/api/v1/info'
    try:
        response = requests.get(
            url=url,
            headers=headers,
            params={
                'quantity': 1
            }
        )
    except:
        logger.error(f'Ошибка при получении артикулов: {traceback.format_exc()}')
        return []
    articles = []
    for price in response.json():
        if 'nmId' in price:
            articles.append(str(price['nmId']))
    return articles


def get_article_info(article):
    url = 'https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-2162195&regions=80,38,4,64,83,33,68,70,69,30,86,75,40,1,66,110,22,31,48,71,114&nm={}&spp=99'
    for _ in range(3):
        try:
            response = requests.get(
                url=url.format(article),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
                }
            ).json()
            if 'data' in response and 'products' in response['data'] and len(response['data']['products']) > 0:
                for product in response['data']['products']:
                    if 'id' in product and str(product['id']) == article:
                        price = None
                        if 'priceU' in product:
                            price = product['priceU']
                        salePrice = None
                        if 'salePriceU' in product:
                            salePrice = product['salePriceU']
                        percent, percent_wb = 0, None
                        if 'extended' in product and 'basicSale' in product['extended']:
                            percent = product['extended']['basicSale']
                        if 'extended' in product and 'clientSale' in product['extended']:
                            percent_wb = product['extended']['clientSale']
                        name = None
                        if 'name' in product:
                            name = product['name']
                        price_full = None
                        if 'priceU' in product:
                            price_full = product['priceU']
                        if price is not None and salePrice is not None and percent_wb is not None:
                            return [
                                str(price), str(salePrice), percent, percent_wb, name, price_full
                            ]
        except:
            continue
    return None


def change_price(article, price):
    headers = {
        'Authorization': config.get('SETTINGS', 'wb_token')
    }
    url = 'https://suppliers-api.wildberries.ru/public/api/v1/prices'
    try:
        response = requests.post(
            url=url,
            headers=headers,
            data=json.dumps([{
                'nmId': int(article),
                'price': float(price)
            }])
        ).json()
    except:
        logger.error(f'Ошибка при получении артикулов: {traceback.format_exc()}')
        return [False, f'\n\nОшибка при получении артикулов: {traceback.format_exc()}']
    if 'errors' in response:
        text = '\nСписок ошибок:\n\n'
        for error in response['errors']:
            text += f'<code>{error}</code>\n'
        return [False, text]
    if len(response) > 0 and not 'errors' in response:
        return [True]
    return [False, '']


def change_percent(article, percent):
    headers = {
        'Authorization': config.get('SETTINGS', 'wb_token')
    }
    url = 'https://suppliers-api.wildberries.ru/public/api/v1/updateDiscounts'
    try:
        response = requests.post(
            url=url,
            headers=headers,
            data=json.dumps([{
                'nm': int(article),
                'discount': int(percent)
            }])
        ).json()
    except:
        logger.error(f'Ошибка при получении артикулов: {traceback.format_exc()}')
        return [False, f'\n\nОшибка при получении артикулов: {traceback.format_exc()}']
    if 'errors' in response:
        text = '\nСписок ошибок:\n\n'
        for error in response['errors']:
            text += f'<code>{error}</code>\n'
        return [False, text]
    if len(response) > 0 and not 'errors' in response:
        return [True]
    return [False, '']


@bot.message_handler(commands=['start'], func=lambda message: message.from_user.id in
                     [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')])
def command_start(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        telebot.types.KeyboardButton(text='Список артикулов')
    )
    bot.send_message(
        message.from_user.id,
        text='Выберите действие',
        reply_markup=keyboard
    )


@bot.message_handler(content_types=['text'], func=lambda message: message.from_user.id in
                     [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')] and
                     message.text == 'Список артикулов')
def command_get_articles(message):
    msg = bot.send_message(
        message.from_user.id,
        text='🔍 Получаю список артикулов...'
    )
    articles = get_prices()
    if len(articles) > 0:
        bot.edit_message_text(
            '✅ Нашел следующие артикулы',
            message.from_user.id,
            msg.message_id,
            parse_mode='html'
        )
        for article in articles:
            article_info = get_article_info(article)
            if article_info is None:
                continue
            keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                telebot.types.InlineKeyboardButton(
                    text='Изменить 👇', callback_data='None'
                )
            )
            keyboard.add(
                telebot.types.InlineKeyboardButton(
                    text='Цена.Клиента', callback_data=f'cprice_{article}_{article_info[2]}_{article_info[3]}'
                ),
                telebot.types.InlineKeyboardButton(
                    text='Цена.Акция', callback_data=f'cprice_{article}_{article_info[2]}_No'
                )
            )
            keyboard.add(
                telebot.types.InlineKeyboardButton(
                    text='Процент', callback_data=f'cperc_{article}_{article_info[2]}_{article_info[3]}'
                )
            )
            bot.send_message(
                message.from_user.id,
                text=f'Артикул <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a>\n\n'
                     f'Цена без скидки: <code>{article_info[0][:-2]}</code>\n'
                     f'Скидка: <code>{article_info[2]}</code>\n'
                     f'Скидка WB: <code>{article_info[3]}</code>\n'
                     f'Цена: <code>{article_info[1][:-2]}</code>',
                parse_mode='html',
                reply_markup=keyboard
            )
    else:
        bot.edit_message_text(
            '❌ Не удалось найти артикулы, попробуйте команду <code>/find_article [Артикул]</code>',
            message.from_user.id,
            msg.message_id,
            parse_mode='html'
        )


@bot.callback_query_handler(func=lambda call: call.from_user.id in
                            [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')] and
                            call.data.startswith('cprice_'))
def callback_change_price(call):
    article = call.data.split('_')[1]
    percent = call.data.split('_')[2]
    percent_wb = call.data.split('_')[3]
    keyboard = telebot.types.ReplyKeyboardMarkup()
    keyboard.add(
        telebot.types.KeyboardButton(
            'Отменить'
        )
    )
    if percent_wb != 'No':
        msg = bot.send_message(
            call.from_user.id,
            text=f'Изменение цены <b>с учетом</b> скидки WB\n\n'
                 f'Введите новую цену для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a>',
            parse_mode='html',
            reply_markup=keyboard
        )
    else:
        msg = bot.send_message(
            call.from_user.id,
            text=f'Изменение цены <b>без учета</b> скидки WB\n\n'
                 f'Введите новую цену для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a>',
            parse_mode='html',
            reply_markup=keyboard
        )
    bot.register_next_step_handler(msg, func_change_price, article, percent, percent_wb)


def func_change_price(message, article, percent, percent_wb):
    price = message.text
    if price == 'Отменить':
        keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(
            telebot.types.KeyboardButton(text='Список артикулов')
        )
        bot.send_message(
            message.from_user.id,
            text='Действие отменено',
            reply_markup=keyboard
        )
        bot.clear_step_handler_by_chat_id(chat_id=message.from_user.id)
        return
    if not price.strip().isdigit():
        msg = bot.send_message(
            message.from_user.id,
            text='Введите целое число!'
        )
        bot.register_next_step_handler(msg, func_change_price, article, percent, percent_wb)
    else:
        if percent_wb != 'No':
            if percent_wb != 100 and percent != 100:
                new_price = (int(price)+0.99) / (100 - int(percent_wb)) * 100
                new_price = int(new_price / (100 - int(percent)) * 100)
            else:
                new_price = price
        else:
            new_price = int((int(price)+0.99) / (100 - int(percent)) * 100)
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text='Изменить цену', callback_data='None'
            )
        )
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text='Да', callback_data=f'chpriceY_{article}_{new_price}'
            ),
            telebot.types.InlineKeyboardButton(
                text='Нет', callback_data=f'chpriceN_{article}'
            )
        )
        article_info = get_article_info(article)
        if percent_wb != 'No':
            bot.send_message(
                message.from_user.id,
                text=f'<a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> {article_info[4]}\n'
                     f'Скидка: {article_info[2]}% Скидка WB: {article_info[3]}%\n'
                     f'Было - Цена: {str(article_info[5])[:-2]} = {str(article_info[1])[:-2]}\n'
                     f'Будет - Цена: {new_price} = {price}\n\n'
                     f'Подтвердите изменение',
                reply_markup=keyboard,
                parse_mode='html'
            )
        else:
            bot.send_message(
                message.from_user.id,
                text=f'<a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> {article_info[4]}\n'
                     f'Скидка: {article_info[2]}%\n'
                     f'Было - Цена: {str(article_info[5])[:-2]} = {str(article_info[1])[:-2]}\n'
                     f'Будет - Цена: {new_price} = {price}\n\n'
                     f'Подтвердите изменение',
                reply_markup=keyboard,
                parse_mode='html'
            )


@bot.callback_query_handler(func=lambda call: call.from_user.id in
                            [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')] and
                            call.data.startswith('chpriceY_'))
def callback_change_price_yes(call):
    article, price = call.data.split('_')[1], call.data.split('_')[2]
    result = change_price(article, price)
    if result[0]:
        bot.edit_message_text(
            f'Успешно изменил цену для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> на {price}',
            call.from_user.id,
            call.message.message_id,
            parse_mode='html'
        )
    else:
        bot.edit_message_text(
            f'Не удалось изменить цену для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> на {price}' + result[1],
            call.from_user.id,
            call.message.message_id,
            reply_markup=None,
            parse_mode='html'
        )
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        telebot.types.KeyboardButton(text='Список артикулов')
    )
    bot.send_message(
        call.from_user.id,
        text='Выберите действие',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.from_user.id in
                            [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')] and
                            call.data.startswith('chpriceN_'))
def callback_change_price_no(call):
    article = call.data.split('_')[1]
    bot.edit_message_text(
        f'Измение цены для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> отменено',
        call.from_user.id,
        call.message.message_id,
        reply_markup=None,
        parse_mode='html'
    )
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        telebot.types.KeyboardButton(text='Список артикулов')
    )
    bot.send_message(
        call.from_user.id,
        text='Выберите действие',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.from_user.id in
                            [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')] and
                            call.data.startswith('cperc_'))
def callback_change_percent(call):
    article = call.data.split('_')[1]
    percent = call.data.split('_')[2]
    percent_wb = call.data.split('_')[3]
    keyboard = telebot.types.ReplyKeyboardMarkup()
    keyboard.add(
        telebot.types.KeyboardButton(
            'Отменить'
        )
    )
    msg = bot.send_message(
        call.from_user.id,
        text=f'Введите новый процент для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a>',
        parse_mode='html',
        reply_markup=keyboard
    )
    bot.register_next_step_handler(msg, func_change_percent, article, percent, percent_wb)


def func_change_percent(message, article, percent, percent_wb):
    price = message.text
    if price == 'Отменить':
        keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(
            telebot.types.KeyboardButton(text='Список артикулов')
        )
        bot.send_message(
            message.from_user.id,
            text='Действие отменено',
            reply_markup=keyboard
        )
        bot.clear_step_handler_by_chat_id(chat_id=message.from_user.id)
        return
    if not price.strip().isdigit():
        msg = bot.send_message(
            message.from_user.id,
            text='Введите целое число!'
        )
        bot.register_next_step_handler(msg, func_change_price, article, percent, percent_wb)
    else:
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text='Изменить процент', callback_data='None1'
            )
        )
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                text='Да', callback_data=f'chpercentY_{article}_{price}'
            ),
            telebot.types.InlineKeyboardButton(
                text='Нет', callback_data=f'chpercentN_{article}'
            )
        )
        article_info = get_article_info(article)
        new_price = (int(str(article_info[0][:-2]))) / (100 - int(price)) * 100
        new_price = int(new_price / (100 - int(article_info[3])) * 100)
        bot.send_message(
            message.from_user.id,
            text=f'<a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> {article_info[4]}\n'
                 f'Скидка: {article_info[2]}% Скидка WB: {article_info[3]}%\n'
                 f'Было {article_info[2]}% - Цена: {str(article_info[5])[:-2]} = {str(article_info[1])[:-2]}\n'
                 f'Будет {price}% - Цена: {str(article_info[5])[:-2]} = {new_price}\n\n'
                 f'Подтвердите изменение',
            reply_markup=keyboard,
            parse_mode='html'
        )


@bot.callback_query_handler(func=lambda call: call.from_user.id in
                            [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')] and
                            call.data.startswith('chpercentY_'))
def callback_change_percent_yes(call):
    article, percent = call.data.split('_')[1], call.data.split('_')[2]
    result = change_percent(article, percent)
    if result[0]:
        bot.edit_message_text(
            f'Успешно изменил скидку для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> на {percent}',
            call.from_user.id,
            call.message.message_id,
            parse_mode='html'
        )
    else:
        bot.edit_message_text(
            f'Не удалось изменить скидку для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> на {percent}' + result[1],
            call.from_user.id,
            call.message.message_id,
            reply_markup=None,
            parse_mode='html'
        )
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        telebot.types.KeyboardButton(text='Список артикулов')
    )
    bot.send_message(
        call.from_user.id,
        text='Выберите действие',
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.from_user.id in
                            [int(admin.strip()) for admin in config.get('SETTINGS', 'users').split(',')] and
                            call.data.startswith('chpercentN_'))
def callback_change_percent_no(call):
    article = call.data.split('_')[1]
    bot.edit_message_text(
        f'Измение цены для артикула <a href="https://www.wildberries.ru/catalog/{article}/detail.aspx?targetUrl=SP">{article}</a> отменено',
        call.from_user.id,
        call.message.message_id,
        reply_markup=None,
        parse_mode='html'
    )
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        telebot.types.KeyboardButton(text='Список артикулов')
    )
    bot.send_message(
        call.from_user.id,
        text='Выберите действие',
        reply_markup=keyboard
    )


if __name__ == '__main__':
    while True:
        try:
            bot.polling()
        except Exception as error:
            logger.error(traceback.format_exc())
            time.sleep(1)