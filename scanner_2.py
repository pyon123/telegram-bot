import mysql.connector
from mysql.connector import Error
import subprocess
import requests
import os
import logging
from datetime import datetime, timedelta
import concurrent.futures
import time

# Set up logging
logging.basicConfig(filename='scanner.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger = logging.getLogger()
logger.addHandler(console_handler)


# Database configuration
db_config = {
    'user': 'leakeruser',
    'password': 'leakerpassword',
    'host': 'localhost',
    'database': 'leaker',
}

# VirusTotal API key
api_key = 'a1d6a23afba7459e360d103cf3a82ef80d9f9ca21de39c0b05515858defa6425'

# Telegram configuration
telegram_token = '6769427343:AAHC0V7zhxApKfcUQXO7DJ817By4u1OrTck'
telegram_chat_id = '-4066060611'

# Connect to the MySQL database
def connect_to_db(config):
    try:
        conn = mysql.connector.connect(**config)
        if conn.is_connected():
            logging.info("Successfully connected to the database.")
            return conn
    except Error as e:
        logging.error(f"Error connecting to the database: {e}")
        return None

# Get domains to scan
def get_domains_to_scan(conn):
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT * FROM scanner_domains 
        WHERE subdomains_discovered=0 OR 
        (subdomains_discovered=1 AND last_dirsearch_scan <= %s)
    """
    last_scan_threshold = datetime.now() - timedelta(days=1)
    logging.info(f"Looking for domains not scanned since: {last_scan_threshold}")
    cursor.execute(query, (last_scan_threshold,))
    domains = cursor.fetchall()
    if not domains:
        logging.info("No domains found to scan.")
    for domain in domains:
        logging.info(f"Domain found to scan: {domain['domain']}")
    cursor.close()
    return domains
# Update domain after subdomain discovery
def update_domain_after_discovery(conn, domain_id):
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE scanner_domains 
        SET subdomains_discovered=1, last_scanned=%s 
        WHERE id=%s
    """, (now, domain_id))
    conn.commit()
    cursor.close()

# Update domain after dirsearch scan
def update_domain_after_dirsearch(conn, domain_id):
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE scanner_domains 
        SET last_dirsearch_scan=%s 
        WHERE id=%s
    """, (now, domain_id))
    conn.commit()
    cursor.close()

# Save subdomains to the database
def save_subdomains(conn, domain_id, subdomains):
    cursor = conn.cursor()
    for subdomain in subdomains:
        cursor.execute("""
            INSERT INTO scanner_domains_subdomains (domain_id, subdomain) 
            VALUES (%s, %s)
        """, (domain_id, subdomain))
    conn.commit()
    cursor.close()

# Save dirsearch result to the database
def save_dirsearch_result(conn, domain_id, path, status_code):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dirsearch_results (domain_id, path, status_code) 
        VALUES (%s, %s, %s)
    """, (domain_id, path, status_code))
    conn.commit()
    cursor.close()

# Send a message to Telegram
def send_telegram_message(message):
    send_url = f'https://api.telegram.org/bot{telegram_token}/sendMessage'
    requests.post(send_url, data={'chat_id': telegram_chat_id, 'text': message})

def find_newest_report(domain):
    report_dir = 'reports'
    report_files = [f for f in os.listdir(report_dir) if f.startswith(f"_{domain}") and f.endswith('.txt')]
    if not report_files:
        return None
    newest_report = max(report_files, key=lambda x: os.path.getctime(os.path.join(report_dir, x)))
    return os.path.join(report_dir, newest_report)


def move_report_to_public(report_path, domain):
    public_report_path = f"/var/www/html/reports/{domain}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_dirsearch.txt"
    os.rename(report_path, public_report_path)
    return public_report_path

def run_dirsearch(args):
    conn, domain_id, domain = args
    report_dir = 'reports'
    command = ["dirsearch", "-u", domain, "-i", "200", "--format=plain", "--log=", report_dir]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    logging.info(f"dirsearch process completed for domain: {domain}")
    logging.info(f"STDOUT: {stdout.decode('utf-8')}")
    logging.info(f"STDERR: {stderr.decode('utf-8')}")

    if process.returncode == 0:
        # Log expected report file name and contents of the report directory
        expected_report_file = f"_{domain}.txt"
        logging.info(f"Expected report file name: {expected_report_file}")
        logging.info(f"Contents of report directory '{report_dir}': {os.listdir(report_dir)}")

        # Wait for the report file to be generated
        report_path = None
        for _ in range(10):  # Retry for a certain number of times
            report_path = find_newest_report(domain)
            if report_path:
                logging.info(f"Report file found for domain {domain}: {report_path}")
                break
            time.sleep(1)  # Wait a bit before retrying

        if report_path is None:
            logging.error(f"No report file found for domain: {domain}")
            return

        # Parse the dirsearch output file for 200 status code paths
        with open(report_path, 'r') as file:
            paths_found = [line.strip() for line in file.readlines() if "200" in line]

        # If paths are found, send a single message with all paths
        if paths_found:
            paths_message = f"200 status paths found for {domain}:\n" + "\n".join(paths_found)
            send_telegram_message(paths_message)
        else:
            send_telegram_message(f"No 200 status paths found for {domain}.")

        # Move the report to the public directory and send the link
        public_report_path = move_report_to_public(report_path, domain)
        report_link = f"http://206.188.196.162/reports/{os.path.basename(public_report_path)}"
        send_telegram_message(f"Report for {domain} is available at: {report_link}")
    else:
        logging.error(f"dirsearch encountered an error for domain: {domain} with return code: {process.returncode}")
        logging.error(f"STDOUT: {stdout}")
        logging.error(f"STDERR: {stderr}")



# Get subdomains from VirusTotal
def get_subdomains(api_key, domain):
    url = f"https://www.virustotal.com/api/v3/domains/{domain}/subdomains"
    headers = {
        "x-apikey": api_key
    }
    subdomains = []
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        json_response = response.json()
        subdomains_list = json_response['data']
        for subdomain in subdomains_list:
            subdomains.append(subdomain['id'])
    else:
        logging.error(f"Error getting subdomains for {domain}: {response.text}")
    return subdomains

# Main function
def main():
    conn = connect_to_db(db_config)
    if conn is None:
        return

    domains = get_domains_to_scan(conn)
    logging.info(f"Retrieved {len(domains)} domains to scan.")

    # Create a thread pool executor
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []

        for domain_record in domains:
            domain_id = domain_record['id']
            domain = domain_record['domain']
            subdomains_discovered = domain_record['subdomains_discovered']
            last_dirsearch_scan = domain_record['last_dirsearch_scan']

            if not subdomains_discovered:
                subdomains = get_subdomains(api_key, domain)
                save_subdomains(conn, domain_id, subdomains)
                update_domain_after_discovery(conn, domain_id)
                logging.info(f"Subdomains discovered and saved for domain: {domain}")

            if not last_dirsearch_scan or last_dirsearch_scan <= datetime.now() - timedelta(hours=24):
                # Submit dirsearch tasks to the thread pool
                futures.append(executor.submit(run_dirsearch, (conn, domain_id, domain)))
                subdomains = get_subdomains(api_key, domain)  # Re-fetch subdomains in case of updates
                for subdomain in subdomains:
                    futures.append(executor.submit(run_dirsearch, (conn, domain_id, subdomain)))

        # Wait for all submitted tasks to complete
        concurrent.futures.wait(futures)

        for domain_record in domains:
            domain_id = domain_record['id']
            update_domain_after_dirsearch(conn, domain_id)
            logging.info(f"Dirsearch scan completed for domain: {domain_record['domain']}")

    logging.info("Scanning process completed.")

if __name__ == "__main__":
    main()