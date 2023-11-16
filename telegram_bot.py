import json
import mysql.connector
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import utc
from telegram import ReplyKeyboardMarkup
import time

MYSQL_CONFIG = {
    'user': 'leakeruser',
    'password': 'leakerpassword',
    'host': 'localhost',
    'database': 'leaker',
    'raise_on_warnings': True
}

def get_db_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)




def force_search_command(update: Update, context: CallbackContext):
    update.message.reply_text("Initiating forced search for all terms. Please wait.")
    force_search_all_terms()
    update.message.reply_text("Forced search complete.")

def parse_json_sequence(json_data, term):  # Added term parameter
    records = []
    fingerprints_seen = set()

    for record in json_data:
        fingerprint = record.get('event_fingerprint')
        if fingerprint in fingerprints_seen:
            continue
        fingerprints_seen.add(fingerprint)

        event_type = record.get('event_type')
        event_source = record.get('event_source')
        ip = record.get('ip')
        host = record.get('host')
        summary = record.get('summary')
        time_str = record.get('time')

        # Convert ISO 8601 time to MySQL DATETIME format
        if time_str:
            try:
                # Truncate the time string to limit the fractional seconds to 6 digits
                time_str = time_str[:26] + 'Z' if len(time_str) > 26 else time_str
                # Parse the time string to a datetime object
                time_obj = datetime.fromisoformat(time_str.rstrip('Z'))
                # Convert to UTC and format to a string that MySQL expects
                time_str = time_obj.replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            except ValueError:
                logging.error(f"Invalid datetime format for time: {time_str}")
                time_str = None

        records.append({
            'resource_id': fingerprint,
            'events_summary': summary,
            'ip': ip,
            'event_source': event_source,
            'host': host,
            'fingerprints': [fingerprint],
            'time': time_str,  # Updated to the converted time string
            'origin_keyword': term  # Add the origin keyword to the record
        })

    return records


def force_search_all_terms():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT term FROM search_terms WHERE active = 1')
    active_terms = cursor.fetchall()

    for term_tuple in active_terms:
        term = term_tuple[0]
        try:
            results = search_leakix(term)
            records = parse_json_sequence(results, term)  # Modified to include term
            insert_into_database(records, cursor, term)  # Modified to include term
            conn.commit()
            logging.info(f"Search complete for term: {term}")
        except Exception as e:
            logging.error(f"An error occurred while searching for term {term}: {e}")
        time.sleep(3)  # Sleep to respect the rate limit

    conn.close()


# Function to get the main command keyboard
def get_main_keyboard():
    keyboard = [
        ['/add', '/list'],
        ['/delete', '/help']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram Bot Token
TELEGRAM_TOKEN = '6769427343:AAHC0V7zhxApKfcUQXO7DJ817By4u1OrTck'
# Leakix API Key
LEAKIX_API_KEY = '4jZVf8WSyHQWNbXbV9UMfHIKpbzg7xxhsKdjENQPrVdCruFx'

# Database connection
DATABASE = 'leakix_results.db'


# Checks if the results are unique to the DB
def check_new_unique_results(results, cursor=None):
    own_connection = False
    if cursor is None:
        own_connection = True
        conn = get_db_connection()
        cursor = conn.cursor()

    new_unique_results = []

    for result in results:
        cursor.execute('SELECT COUNT(*) FROM results_table WHERE resource_id = %s', (result['resource_id'],))
        if cursor.fetchone()[0] == 0:
            new_unique_results.append(result)

    if own_connection:
        conn.commit()
        conn.close()

    return new_unique_results


# Formats results to be sent to TG Channel
def format_results_message(results):
    messages = ["Ã°Å¸â€ *New Leakix Search Results*"]
    for result in results:
        message = f"Resource ID: {result['resource_id']}\nSummary: {result['events_summary']}\nIP: {result['ip']}\nSource: {result['event_source']}\nHost: {result['host']}\nFingerprints: {', '.join(result['fingerprints'])}\n---"
        messages.append(message)
    return '\n'.join(messages)


# Function to search Leakix
def search_leakix(search_term):
    logging.info(f"Searching Leakix for term: {search_term}")
    base_url = "https://leakix.net/search"
    headers = {
        'accept': 'application/json',
        'api-key': LEAKIX_API_KEY
    }
    time_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')

    results = []
    for field in ['events.summary', 'host']:
        query = f"+{field}:~.*{search_term}~.* +time:>{time_date}"
        params = {
            'scope': "leaks",
            'q': query
        }
        response = requests.get(base_url, headers=headers, params=params)
        logging.info(f"Leakix API response status for {field}: {response.status_code}")
        if response.status_code == 200:
            logging.info(f"Leakix API response data for {field}: {response.text}")
            results.extend(response.json())
        else:
            logging.error(f"Leakix API request failed for {field}: {response.text}")
            response.raise_for_status()

    return results

# Function to parse JSON from Leakix


# Function to insert data into the database
def insert_into_database(records, cursor=None, term=None):  # Added term parameter
    own_connection = False
    if cursor is None:
        own_connection = True
        conn = get_db_connection()
        cursor = conn.cursor()

    for record in records:
        try:
            cursor.execute('''
            INSERT INTO results_table (resource_id, events_summary, ip, event_source, host, fingerprints, time, origin_keyword)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                record['resource_id'],
                record['events_summary'],
                record['ip'],
                record['event_source'],
                record['host'],
                json.dumps(record['fingerprints']),
                record['time'],
                record['origin_keyword']  # Add the origin keyword to the insert statement
            ))
            logging.info(f"Inserted record with resource_id: {record['resource_id']}")
        except mysql.connector.IntegrityError as e:
            logging.error(f"IntegrityError for resource_id {record['resource_id']}: {e}")
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            continue

    if own_connection:
        conn.commit()
        conn.close()


# Function to handle the '/start' command
def start(update: Update, context: CallbackContext):
    reply_markup = get_main_keyboard()
    update.message.reply_text(
        'Hi! I am your Leakix search assistant. What would you like to do?',
        reply_markup=reply_markup
    )


# Function to handle the '/help' command
def help_command(update: Update, context: CallbackContext):
    reply_markup = get_main_keyboard()
    update.message.reply_text(
        'Here are the commands you can use:\n'
        '/add - Add a new search term.\n'
        '/list - List all your search terms.\n'
        '/delete - Delete an existing search term.\n'
        'Just tap a button below to get started.',
        reply_markup=reply_markup
    )


# Function to add a search term
def add_term(update: Update, context: CallbackContext):
    term = ' '.join(context.args)
    if not term:
        update.message.reply_text('Please provide a search term.')
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO search_terms (term) VALUES (%s)', (term,))
        conn.commit()
        update.message.reply_text(f'Search term "{term}" added and will be searched twice a day.')
    except mysql.connector.IntegrityError:
        update.message.reply_text('This search term already exists.')
    finally:
        conn.close()


# Function to list search terms with pagination
# Function to list search terms with pagination and delete option
def list_terms(update: Update, context: CallbackContext):
    print('========== list terms ==========')
    query = update.callback_query
    page = int(query.data.split('_')[1]) if query else 0

    page_size = 5
    offset = page * page_size
    print(page)
    print(page_size)
    print(offset)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, term FROM search_terms LIMIT %s OFFSET %s', (page_size, offset))
    terms = cursor.fetchall()

    keyboard = [[InlineKeyboardButton(term_text, callback_data=f'noop_{term_id}'),
                 InlineKeyboardButton('❌', callback_data=f'delete_{term_id}')] for term_id, term_text in terms]

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton('⬅️¸ Previous', callback_data=f'list_{page-1}'))
    if len(terms) == page_size:
        navigation_buttons.append(InlineKeyboardButton('Next ➡️¸', callback_data=f'list_{page+1}'))
    if navigation_buttons:
        keyboard.append(navigation_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.edit_message_text('Search Terms:', reply_markup=reply_markup)
    else:
        update.message.reply_text('Search Terms:', reply_markup=reply_markup)

    conn.close()


# Function to delete a search term
def delete_term(update: Update, context: CallbackContext):
    query = update.callback_query
    term_id = query.data.split('_')[1]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM search_terms WHERE id = %s', (term_id,))
    conn.commit()
    conn.close()

    query.answer('Search term deleted.')
    list_terms(update, context)  # Refresh the list


# Function to handle messages
def handle_message(update: Update, context: CallbackContext):
    update.message.reply_text('Please use a command to interact with the bot.')


# Function to handle errors
def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


# Function to edit a search term
def edit_term(update: Update, context: CallbackContext):
    query = update.callback_query
    term_id = query.data.split('_')[1]
    # Here you can prompt the user to enter the new term or provide further instructions
    query.answer('Send me the new search term.')
    # Store the term_id in the context to use it after the user sends the new term
    context.user_data['edit_term_id'] = term_id
    # Switch to a state where you expect the user to enter the new term
    # You would need to implement a ConversationHandler for this part


# Function to perform scheduled searches

def scheduled_search(context: CallbackContext):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT term FROM search_terms WHERE active = 1')
    active_terms = cursor.fetchall()

    for term_tuple in active_terms:
        term = term_tuple[0]
        try:
            results = search_leakix(term)
            records = parse_json_sequence(results, term)
            new_results = check_new_unique_results(records, cursor)

            unpublished_results = [result for result in new_results if not result['published']]
            if unpublished_results:
                message = format_results_message(unpublished_results)
                context.bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode='Markdown')
                mark_results_as_published(unpublished_results, cursor)

            time.sleep(3)
        except Exception as e:
            logging.error(f"An error occurred while searching for term {term}: {e}")

    conn.commit()
    conn.close()

def mark_results_as_published(results, cursor):
    resource_ids = [result['resource_id'] for result in results]
    query = 'UPDATE results_table SET published = TRUE WHERE resource_id IN (%s)'
    format_strings = ','.join(['%s'] * len(resource_ids))
    cursor.execute(query % format_strings, tuple(resource_ids))

# Main function to start the bot
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("add", add_term, pass_args=True))
    dp.add_handler(CommandHandler("list", list_terms))
    dp.add_handler(CallbackQueryHandler(list_terms, pattern='^list_.*$'))
    dp.add_handler(CallbackQueryHandler(delete_term, pattern='^delete_\\d+$'))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_error_handler(error)
    dp.add_handler(CommandHandler('forcesearch', force_search_command))

    updater.start_polling()
    scheduler = BackgroundScheduler(timezone=utc, job_defaults={'misfire_grace_time': 15 * 60})
    scheduler.add_job(scheduled_search, 'interval', hours=12, args=(CallbackContext(dp),))
    scheduler.start()

    updater.idle()


if __name__ == '__main__':
    logging.info("Starting the bot")
    main()
