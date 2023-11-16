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
        update.message.reply_text(f'{type} "{term}" already exists.')
    else:
        insert_query = 'INSERT INTO search_terms (term, type) VALUES (%s, %s);'
        db.execute_query(insert_query, (term, type))
        update.message.reply_text(f'{type} "{term}" is added and will be searched twice a day.')

def delete_term(update: Update, term: str, type: str):
    logger.info('delete_term type: "%s", term: "%s"', type, term)

    check_query = 'SELECT id FROM search_terms WHERE term = %s AND type = %s;'
    existing_record = db.fetch_data(check_query, (term, type))

    if existing_record:
        delete_query = 'DELETE FROM search_terms WHERE term = %s AND type = %s;'
        db.execute_query(delete_query, (term, type))
        update.message.reply_text(f'{type} "{term}" has been deleted.')
    else:
        update.message.reply_text(f'{type} "{term}" does not exist.')

def list_terms(update: Update, type: str):
    callback_query = update.callback_query
    page = int(callback_query.data.split('_')[1]) if callback_query else 0

    logger.info('list_terms type: "%s", page: "%s"', type, page)

    page_size = 5
    offset = page * page_size
    query = 'SELECT id, term FROM search_terms where type = %s LIMIT %s OFFSET %s'
    terms = db.fetch_data(query, (type, page_size, offset))

    keyboard = [[InlineKeyboardButton(term_text, callback_data=f'noop_{term_id}'),
                 InlineKeyboardButton('❌', callback_data=f'deleteTerm_{page}_{term_id}_{type}')] for term_id, term_text in terms]

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton('⬅️¸ Previous', callback_data=f'{type}s_{page-1}'))
    if len(terms) == page_size:
        navigation_buttons.append(InlineKeyboardButton('Next ➡️¸', callback_data=f'{type}s_{page+1}'))
    if navigation_buttons:
        keyboard.append(navigation_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        callback_query.edit_message_text('Search Terms:', reply_markup=reply_markup)
    else:
        update.message.reply_text('Search Terms:', reply_markup=reply_markup)


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

def delete_term_by_id(update: Update, context: CallbackContext):
    callback_query = update.callback_query
    if callback_query is None:
        callback_query.answer('Please provide a ID.')

    page = int(callback_query.data.split('_')[1]) if callback_query else 0
    id = int(callback_query.data.split('_')[2]) if callback_query else 0
    type = callback_query.data.split('_')[3]
    
    logger.info(f'delete_term_by_id ==> page: {page}, id: {id}, type: {type}')

    db.execute_query('DELETE FROM search_terms WHERE id = %s', (id,))

    callback_query.answer('Search term deleted.')

    list_terms(update, type)
    

if __name__ == '__main__':
    logger.info("Starting the bot")

    updater = Updater(os.getenv('TELEGRAM_TOKEN'), use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("add_domain", add_domain, pass_args=True))
    dp.add_handler(CommandHandler("domains", domains))
    dp.add_handler(CallbackQueryHandler(domains, pattern='^domains_.*$'))
    dp.add_handler(CommandHandler("delete_domain", delete_domain, pass_args=True))

    dp.add_handler(CommandHandler("add_keyword", add_keyword, pass_args=True))
    dp.add_handler(CommandHandler("keywords", keywords))
    dp.add_handler(CallbackQueryHandler(keywords, pattern='^keywords_.*$'))
    dp.add_handler(CommandHandler("delete_keyword", delete_keyword, pass_args=True))

    dp.add_handler(CallbackQueryHandler(delete_term_by_id, pattern='^deleteTerm_.*$'))

    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()
