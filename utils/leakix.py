import os
from utils.logger import logger
from utils.mysqlLib import MySQL
from datetime import datetime, timedelta, timezone
import requests
import time
import json

BASE_URL = "https://leakix.net/search"

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
                logger.error(f"Invalid datetime format for time: {time_str}")
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

def search_leakix(search_term):
    logger.info(f"Searching Leakix for term: {search_term}")
    headers = {
        'accept': 'application/json',
        'api-key': os.getenv('LEAKIX_API_KEY')
    }
    time_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')

    results = []
    for field in ['events.summary', 'host']:
        query = f"+{field}:~.*{search_term}~.* +time:>{time_date}"
        params = {
            'scope': "leaks",
            'q': query
        }
        response = requests.get(BASE_URL, headers=headers, params=params)
        logger.info(f"Leakix API response status for {field}: {response.status_code}")
        if response.status_code == 200:
            # logger.info(f"Leakix API response data for {field}: {response.text}")
            results.extend(response.json())
        else:
            logger.error(f"Leakix API request failed for {field}: {response.text}")
            response.raise_for_status()

    return results

def search_all(db: MySQL):
    active_terms = db.fetch_data('SELECT term FROM search_terms WHERE active = 1')

    for term_tuple in active_terms:
        term = term_tuple['term']
        try:
            results = search_leakix(term)
            records = parse_json_sequence(results, term)
            for record in records:
                if record['events_summary'] in ['DotEnvConfigPlugin', 'YiiDebugPlugin', 'GitConfigHttpPlugin', 'JiraPlugin', 'MongoOpenPlugin', 'DockerRegistryHttpPlugin', 'ElasticSearchOpenPlugin']:
                    continue

                exsiting_record = db.fetch_data('SELECT id FROM results_table WHERE resource_id = %s;', (record['resource_id'],))
                if not exsiting_record:
                    db.execute_query('''
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
                    logger.info(f"Inserted record with resource_id: {record['resource_id']}")
                else:
                    logger.info(f"Existing record with resource_id: {record['resource_id']}")
            logger.info(f"Search complete for term: {term}")
            # return records
        except Exception as e:
            logger.error(f"An error occurred while searching for term {term}: {e}")
        time.sleep(3)  # Sleep to respect the rate limit
