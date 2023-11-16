import requests
import mysql.connector
from mysql.connector import Error
import time 

# Replace 'your_api_key' with your actual CoinMarketCap API key
api_key = 'aa47acd6-e73f-4ff8-b87d-7e6e20cb2825'

# Database configuration - replace with your details
db_config = {
    'host': 'localhost',
    'user': 'leakeruser',
    'password': 'leakerpassword',
    'database': 'leaker'
}

# CoinMarketCap API URL for listings and info
cmc_listings_url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
cmc_info_url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/info'

# API headers
headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': api_key,
}

# Connect to the MySQL database
def connect_to_db(config):
    try:
        conn = mysql.connector.connect(**config)
        if conn.is_connected():
            print("Successfully connected to the database.")
            return conn
    except Error as e:
        print(f"Error: {e}")
        return None

# Insert project data into the database
def insert_project_data(conn, project_data):
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO crypto_projects (name, market_cap, trade_volume, url)
        VALUES (%s, %s, %s, %s)
        """
        cursor.executemany(query, project_data)
        conn.commit()
        print(f"Inserted {cursor.rowcount} rows into the database.")
        cursor.close()
    except Error as e:
        print(f"Error: {e}")

# Retrieve the URL or domain for a cryptocurrency
def get_crypto_url(crypto_id):
    params = {'id': crypto_id}
    response = requests.get(cmc_info_url, headers=headers, params=params)
    data = response.json()
    if 'data' in data and str(crypto_id) in data['data']:
        urls = data['data'][str(crypto_id)].get('urls', {}).get('website', [])
        return urls[0] if urls else None
    return None

# Retrieve and filter crypto projects from CoinMarketCap with pagination
def retrieve_and_filter_crypto_data(limit=100):
    filtered_projects = []
    total_logged = 0
    start = 1
    request_count = 0
    start_time = time.time()

    while True:
        current_time = time.time()
        if current_time - start_time >= 60:
            request_count = 0
            start_time = current_time

        if request_count >= 29:
            time.sleep(start_time + 60 - current_time)
            request_count = 0
            start_time = time.time()

        params = {
            'start': start,
            'limit': limit,
            'convert': 'USD'
        }
        response = requests.get(cmc_listings_url, headers=headers, params=params)
        data = response.json()

        if 'data' not in data:
            print(f"Error: 'data' key not found in the response. Response data: {data}")
            break

        cryptos = data['data']
        if not cryptos:
            break

        for crypto in cryptos:
            name = crypto['name']
            market_cap = crypto['quote']['USD']['market_cap']
            trade_volume = crypto['quote']['USD']['volume_24h']

            if market_cap >= 500000 and trade_volume >= 100000:
                request_count += 1
                if request_count >= 29:
                    time.sleep(start_time + 60 - time.time())
                    request_count = 0
                    start_time = time.time()

                url = get_crypto_url(crypto['id'])
                filtered_projects.append((name, market_cap, trade_volume, url))
                total_logged += 1

        start += limit
        request_count += 1
        print(f"Processed {start} cryptos so far...")

    print(f"Total projects logged: {total_logged}")
    return filtered_projects

# Main function to orchestrate the data retrieval and database operations
def main():
    conn = connect_to_db(db_config)
    if conn is None:
        print("Failed to connect to the database.")
        return

    project_data = retrieve_and_filter_crypto_data()
    insert_project_data(conn, project_data)

    conn.close()
    print("Data insertion complete.")

if __name__ == "__main__":
    main()
