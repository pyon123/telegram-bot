from dotenv import load_dotenv
from utils.logger import logger
import os
from telegram import Bot
from utils.mysqlLib import MySQL
import time
from datetime import datetime

load_dotenv()

db = MySQL(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

bot = Bot(token=os.getenv('TELEGRAM_TOKEN'))

def send_telegram_message(message):
    bot.send_message(chat_id=os.getenv('PUBLISH_CHANNEL_ID'), text=message, parse_mode='Markdown')

def escape_markdown(text):
    """Escape markdown special characters"""
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

def publish_search():
    try:
        results = db.fetch_data(
            """
            SELECT * FROM results_table WHERE published = 0
            AND event_source IN (
                'DotEnvConfigPlugin', 'YiiDebugPlugin', 'GitConfigHttpPlugin',
                'JiraPlugin', 'MongoOpenPlugin', 'DockerRegistryHttpPlugin', 'ElasticSearchOpenPlugin'
            )
            """
        )
        if results:
            logger.info(f"Found {len(results)} new unpublished results.")
            for result in results:
                truncated_summary = result['events_summary'][:30] + '...' if len(result['events_summary']) > 30 else result['events_summary']
                logger.info(truncated_summary)
                leakix_url = f"https://leakix.net/host/{result['ip']}"
                message = (
                    f"{escape_markdown(result['event_source'])} found for **{escape_markdown(result['origin_keyword'])}**:\n"
                    f"{escape_markdown(truncated_summary)}\n"
                    f"[Leakix Host]({leakix_url})"
                )
                logger.info(f"Sending message: {message}")
                send_telegram_message(message)

                # update as published
                db.execute_query('UPDATE results_table SET published = 1 WHERE id = %s', (result['id'],))

                time.sleep(3)

    except Exception as e:
        logger.error(f"An error occurred: {e}")

def publish_dirsearch(domain, report_date):
    try:
        logger.info(f'publish domain: {domain}, date: {report_date}')
        results = db.fetch_data('SELECT id, path FROM dirsearch_results WHERE domain = %s AND published = 0', (domain,))
        if results:
            others = db.fetch_data('SELECT path FROM dirsearch_results WHERE domain = %s AND published = 1 limit 1', (domain,))
            paths = ", ".join(
                f"[{result['path'].replace(f'https://{domain}/', '').replace(f'http://{domain}/', '')}]({result['path']})"
                for result in results
            )
            message = (
                f"{domain} / report {report_date} \n"
                f"found {'new' if others else ''} {len(results)} path{'s' if len(results) > 1 else ''} \n"
                f"{paths}"
            )
            logger.info(f'message ========> {message}')
            send_telegram_message(message)

            # update as published
            db.execute_query(
                f"UPDATE dirsearch_results SET published = 1 WHERE id IN ({', '.join(['%s'] * len(results))})",
                tuple(result['id'] for result in results)
            )

            time.sleep(3)

    except Exception as e:
        logger.error(f"publish_dirsearch error occurred: {e}")

def publish_domains():
    try:
        domains = db.fetch_data('SELECT id, domain, last_dirsearch_scan FROM scanner_domains;')
        for domain in domains:
            report_date = domain['last_dirsearch_scan'].strftime("%d/%m/%Y")
            publish_dirsearch(domain['domain'], report_date)

            try:
                sub_domains = db.fetch_data(
                    'SELECT subdomain FROM scanner_domains_subdomains WHERE domain_id = %s;',
                    (domain['id'],)
                )
                for sub_domain in sub_domains:
                    publish_dirsearch(sub_domain['subdomain'], report_date)
            except Exception as e:
                logger.error(f"publish_sub_domains error occurred: {e}")
    except Exception as e:
        logger.error(f"publish_domains error occurred: {e}")

if __name__ == "__main__":
    publish_search()
    publish_domains()
