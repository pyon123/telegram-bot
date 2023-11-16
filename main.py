from dotenv import load_dotenv
from utils.logger import logger
import os
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

load_dotenv()

# Function to get the main command keyboard
def get_main_keyboard():
    keyboard = [
        ['/domain', '/list'],
        ['/delete', '/help']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def help_command(update: Update, context: CallbackContext):
    reply_markup = get_main_keyboard()
    update.message.reply_text(
        'Here are the commands you can use:\n'
        '/domain - Add a new search term type domain.\n'
        '/keyword - Add a new search term type keyword.\n'
        '/list - List all your search terms.\n'
        '/delete - Delete an existing search term.\n'
        'Just tap a button below to get started.',
        reply_markup=reply_markup
    )

# Function for domain
def add_domain(update: Update, context: CallbackContext):
    domain = ' '.join(context.args)
    if not domain:
        update.message.reply_text('Please provide a domain.')
        return

def delete_domain(update: Update, context: CallbackContext):
    domain = ' '.join(context.args)
    if not domain:
        update.message.reply_text('Please provide a domain.')
        return

def domains(update: Update, context: CallbackContext):
    return

# Function for keyword
def add_keyword(update: Update, context: CallbackContext):
    keyword = ' '.join(context.args)
    if not keyword:
        update.message.reply_text('Please provide a keyword.')
        return

def delete_keyword(update: Update, context: CallbackContext):
    keyword = ' '.join(context.args)
    if not keyword:
        update.message.reply_text('Please provide a keyword.')
        return

def keywords(update: Update, context: CallbackContext):
    return

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
