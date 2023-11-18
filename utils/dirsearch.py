import os
from utils.logger import logger
from utils.mysqlLib import MySQL
from datetime import datetime, timedelta
import concurrent.futures
import requests
import subprocess
import json

def store_subdomains(db: MySQL, domain, domain_id):
    url = f"https://www.virustotal.com/api/v3/domains/{domain}/subdomains"
    headers = {
        "x-apikey": os.getenv('VirusTotal_API_KEY')
    }
    subdomains = []
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.error(f"Error getting subdomains for {domain}: {response.text}")
        return []
    
    json_response = response.json()
    subdomains_list = json_response['data']
    for subdomain in subdomains_list:
        # insert subdomain
        existing = db.fetch_data('SELECT id FROM scanner_domains_subdomains WHERE domain_id = %s AND subdomain = %s', (domain_id, subdomain['id']))
        if not existing:
            db.execute_query('INSERT INTO scanner_domains_subdomains (domain_id, subdomain) VALUES (%s, %s)', (domain_id, subdomain['id']))

        subdomains.append(subdomain['id'])
    
    # update domain
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute_query('UPDATE scanner_domains SET subdomains_discovered=1, last_scanned=%s WHERE id = %s', (now, domain_id))

    return subdomains

def run_dirsearch(db: MySQL, domain):
    try:
        report_dir = f'reports/_{domain}'
        os.makedirs(report_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = f"{report_dir}/{timestamp}.json"
        command = ["dirsearch", "-u", domain, "-i", "200", "--format=json", "-o", output_file]
        # process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # stdout, stderr = process.communicate()

        logger.info(f"dirsearch process completed for domain: {domain}")

        if result.returncode != 0:
            logger.error(f"dirsearch encountered an error for domain: {domain} with return code: {result.returncode}")

        logger.info(f"{domain} output path ==> {output_file}")
        with open(output_file, 'r') as json_file:
            data = json_file.read()
            logger.info(f"data ===> {domain}")

        json_output = json.loads(data)
        for result in json_output["results"]:
            path = result["url"]
            status_code = result["status"]
            existing = db.fetch_data('SELECT id FROM dirsearch_results WHERE domain = %s AND path = %s;', (domain, path))
            if not existing:
                 db.execute_query("""
                    INSERT INTO dirsearch_results 
                    (domain, path, status_code, published) 
                    VALUES (%s, %s, %s, 0)
                """, (domain, path, status_code))

    except Exception as e:
        logger.info(f"Error running dirsearch '{domain}': {e}")

def search_all(db: MySQL):
    query = """
        SELECT * FROM scanner_domains 
        WHERE subdomains_discovered=0 OR 
        (subdomains_discovered=1 AND last_dirsearch_scan <= %s)
    """
    last_scan_threshold = datetime.now() - timedelta(days=7)
    logger.info(f"Looking for domains not scanned since: {last_scan_threshold}")

    domains = db.fetch_data(query, (last_scan_threshold,))
    logger.info(f"Retrieved {len(domains)} domains to scan ===> {domains}")

    # Create a thread pool executor
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []

        for domain_record in domains:
            domain_id = domain_record[0]
            domain = domain_record[1]
            last_dirsearch_scan = domain_record[5]

            subdomains = store_subdomains(db, domain, domain_id)
            logger.info(f"Subdomains discovered and saved for domain: {domain}")

            if not last_dirsearch_scan or last_dirsearch_scan <= (datetime.now() - timedelta(days=7)):
                # Submit dirsearch tasks to the thread pool
                futures.append(executor.submit(run_dirsearch, db, domain))

                for subdomain in subdomains:
                    futures.append(executor.submit(run_dirsearch, db, subdomain))

        # Wait for all submitted tasks to complete
        concurrent.futures.wait(futures)

        for domain_record in domains:
            domain_id = domain_record[0]
            # update domain dirsearch
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute_query("""
                UPDATE scanner_domains 
                SET last_dirsearch_scan=%s 
                WHERE id=%s
            """, (now, domain_id))
            logger.info(f"Dirsearch scan completed for domain: {domain_record[1]}")

    logger.info("Scanning process completed.")
