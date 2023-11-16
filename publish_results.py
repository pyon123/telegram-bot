import mysql.connector
import logging
from telegram import Bot
import time

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# MySQL configuration
MYSQL_CONFIG = {
    'user': 'leakeruser',
    'password': 'leakerpassword',
    'host': 'localhost',
    'database': 'leaker',
    'raise_on_warnings': True
}

# Telegram Bot Token and Channel ID
TELEGRAM_TOKEN = '6769427343:AAHC0V7zhxApKfcUQXO7DJ817By4u1OrTck'
CHANNEL_ID = '-4064320353'

# Function to get the database connection
def get_db_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)

# Function to format and send the message to Telegram
def send_telegram_message(bot, message):
    bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode='Markdown')

# Function to retrieve new unpublished results
def get_new_unpublished_results(cursor):
    cursor.execute('SELECT * FROM results_table WHERE published = FALSE')
    return cursor.fetchall()

# Function to mark results as published in the database

def escape_markdown(text):
    """Escape markdown special characters"""
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

def mark_results_as_published(cursor, result_ids):
    if result_ids:
        placeholders = ', '.join(['%s'] * len(result_ids))
        cursor.execute(f"UPDATE results_table SET published = 1 WHERE resource_id IN ({placeholders})", tuple(result_ids))
        logger.info(f"Marked {len(result_ids)} results as published.")

def run_once():
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        logger.info("Connected to the database.")
        results = get_new_unpublished_results(cursor)

        if results:
            logger.info(f"Found {len(results)} new unpublished results.")
            result_ids = []
            for result in results:
                # Ensure the comparison is case-insensitive
                if result['event_source'].lower() == "wpuserenumhttp":
                    logger.info(f"Skipping result with event_source WpUserEnumHTTP: {result['resource_id']}")
                    continue  # Skip results with the event_source "WpUserEnumHTTP"
                
                result_ids.append(result['resource_id'])
                # Truncate the summary to 30 characters
                truncated_summary = result['events_summary'][:30] + '...' if len(result['events_summary']) > 30 else result['events_summary']
                leakix_url = f"https://leakix.net/host/{result['ip']}"
                message = (
                    f"{escape_markdown(result['event_source'])} found for **{escape_markdown(result['origin_keyword'])}**:\n"
                    f"{escape_markdown(truncated_summary)}\n"
                    f"[Leakix Host]({leakix_url})"
                )
                logger.info(f"Sending message: {message}")
                send_telegram_message(bot, message)
                logger.info("Message sent successfully.")
                time.sleep(3)  # Delay to prevent hitting Telegram rate limits
            
            if result_ids:
                mark_results_as_published(cursor, result_ids)
                conn.commit()
                logger.info(f"Published status updated for {len(result_ids)} results.")
        else:
            logger.info("No new unpublished results found.")

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == '__main__':
    logger.info("Running the publication script")
    run_once()
