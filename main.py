from dotenv import load_dotenv
from utils.logger import logger
import os
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from utils.mysqlLib import MySQL
import atexit

load_dotenv()

db = MySQL(host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'))

def cleanup():
    # This function will be called when the program is about to exit
    print("Performing cleanup tasks...")
    db.close_connection()

atexit.register(cleanup)

# Function to get the main command keyboard
def get_main_keyboard():
    keyboard = [
        ['/domains', '/add_domain', '/delete_domain'],
        ['/keywords', '/add_keyword', '/delete_keyword']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def help_command(update: Update, context: CallbackContext):
    reply_markup = get_main_keyboard()
    update.message.reply_text(
        'Here are the commands you can use:\n'
        '/domains - List all domains.\n'
        '/add_domain - Add a new domain.\n'
        '/delete_domain - Delete a domain.\n'
        '/keywords - List all keywards.\n'
        '/add_keyword - Add a new keyword.\n'
        '/delete_keyword - delete a keyword.\n'
        'Just tap a button below to get started.',
        reply_markup=reply_markup
    )

def add_term(update: Update, term: str, type: str):
    logger.info('add_term type: "%s", term: "%s"', type, term)
    check_query = 'SELECT id FROM search_terms WHERE term = %s AND type = %s;'
    existing_record = db.fetch_data(check_query, (term, type))

    if existing_record:
        update.message.reply_text(f'This {type} "{term}" already exists.')
    else:
        insert_query = 'INSERT INTO search_terms (term, type) VALUES (%s, %s);'
        db.execute_query(insert_query, (term, type))
        update.message.reply_text(f'{type} "{term}" is added and will be searched twice a day.')

def delete_term(update: Update, term: str, type: str):
    logger.info('delete_term type: "%s", term: "%s"', type, term)

def list_terms(update: Update, type: str):
    logger.info('list_terms type: "%s"', type)

# Function for domain
def add_domain(update: Update, context: CallbackContext):
    domain = ' '.join(context.args)
    if not domain:
        update.message.reply_text('Please provide a domain.')
        return
    add_term(update, domain, 'domain')

def delete_domain(update: Update, context: CallbackContext):
    domain = ' '.join(context.args)
    if not domain:
        update.message.reply_text('Please provide a domain.')
        return
    delete_term(update, domain, 'domain')

def domains(update: Update, context: CallbackContext):
    list_terms(update, 'domain')

# Function for keyword
def add_keyword(update: Update, context: CallbackContext):
    keyword = ' '.join(context.args)
    if not keyword:
        update.message.reply_text('Please provide a keyword.')
        return
    add_term(update, keyword, 'keyword')

def delete_keyword(update: Update, context: CallbackContext):
    keyword = ' '.join(context.args)
    if not keyword:
        update.message.reply_text('Please provide a keyword.')
        return
    delete_term(update, keyword, 'keyword')

def keywords(update: Update, context: CallbackContext):
    list_terms(update, 'keyword')

if __name__ == '__main__':
    logger.info("Starting the bot")

    updater = Updater(os.getenv('TELEGRAM_TOKEN'), use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("add_domain", add_domain, pass_args=True))
    dp.add_handler(CommandHandler("domains", domains))
    dp.add_handler(CommandHandler("delete_domain", delete_domain, pass_args=True))

    dp.add_handler(CommandHandler("add_keyword", add_keyword, pass_args=True))
    dp.add_handler(CommandHandler("keywords", keywords))
    dp.add_handler(CommandHandler("delete_keyword", delete_keyword, pass_args=True))

    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()
