#!/usr/bin/env python3
import requests
import json
import logging
import time
import mysql.connector
from requests.exceptions import ConnectionError, Timeout, RequestException


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s — %(message)s',
                    datefmt='%Y-%m-%d_%H:%M:%S',
                    handlers=[logging.StreamHandler()])

MAX_RETRIES = 3  # Set the maximum number of retries
BACKOFF_FACTOR = 1.5  # Define backoff factor for exponential delay

def init_db_connection(config):
    return mysql.connector.connect(
        host=config['mysql_host'],
        user=config['mysql_username'],
        password=config['mysql_password'],
        database=config['mysql_database']
    )


def make_request(url, headers, data):
    for i in range(MAX_RETRIES):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
            return response
        except (ConnectionError, Timeout) as e:
            logging.error(f"Connection error or timeout: {e}. Retrying in {BACKOFF_FACTOR ** i} seconds.")
            time.sleep(BACKOFF_FACTOR ** i)
        except RequestException as e:
            logging.error(f"Fatal error encountered: {e}. Exiting.")
            return None
    return None


def create_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS validators_data (
            exchange_rates_id VARCHAR(255),
            network VARCHAR(255),
            suiAddress VARCHAR(255),
            pool_id VARCHAR(255),
            active BOOLEAN,
            epoch INT,
            pool_token_amount BIGINT,
            sui_amount BIGINT,
            PRIMARY KEY(exchange_rates_id, epoch)
        )
    """)

def insert_into_table(cursor, data):
    query = """
         INSERT IGNORE INTO validators_data (exchange_rates_id, network, suiAddress, pool_id, active, epoch, pool_token_amount, sui_amount)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, data)

def fetch_epochs(cursor, exchange_rates_id):
    query = """
        SELECT epoch FROM validators_data WHERE exchange_rates_id = %s
    """
    cursor.execute(query, (exchange_rates_id,))
    rows = cursor.fetchall()
    return [row[0] for row in rows]  # Extract the epochs from the rows

def get_dynamic_fields_paginated(url, exchange_rates_id, next_cursor=None):
    headers = {
        'Content-Type': 'application/json',
    }

    data = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'suix_getDynamicFields',
        'params': [exchange_rates_id, next_cursor] if next_cursor else [exchange_rates_id]
    }

    response = make_request(url, headers, data)

    if response and response.status_code == 200:
        response_json = response.json()
        data = response_json.get('result', {}).get('data', [])
        epochs = [int(item.get('name', {}).get('value')) for item in data] # Conversion to integer
        hasNextPage = response_json.get('result', {}).get('hasNextPage')
        if hasNextPage:
            nextCursor = response_json.get('result', {}).get('nextCursor')
            logging.info(f'ExchangeRatesId: {exchange_rates_id}, hasNextPage: {hasNextPage}, nextCursor: {nextCursor}')
            epochs += get_dynamic_fields_paginated(url, exchange_rates_id, nextCursor) # Recursive call for the next page
        return epochs
    else:
        logging.error('Error fetching data or no data returned.')
        return []

def get_latest_sui_system_state(url):
    headers = {
        'Content-Type': 'application/json',
    }

    data = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'suix_getLatestSuiSystemState',
    }

    response = make_request(url, headers, data)

    if response and response.status_code == 200:
        return response.json()
    else:
        logging.error('Error fetching data or no data returned.')

def get_dynamic_fields(url, exchange_rates_id):
    headers = {
        'Content-Type': 'application/json',
    }

    data = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'suix_getDynamicFields',
        'params': [exchange_rates_id]
    }

    response = make_request(url, headers, data)

    if response and response.status_code == 200:
        return response.json()
    else:
        logging.error('Error fetching data or no data returned.')

def get_dynamic_field_object(url, exchange_rates_id, epoch):
    headers = {
        'Content-Type': 'application/json',
    }

    data = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'suix_getDynamicFieldObject',
        'params': [exchange_rates_id, { 'type': 'u64', 'value': str(epoch) }] # Converted the epoch to a string
    }

    response = make_request(url, headers, data)

    if response and response.status_code == 200:
        return response.json()
    else:
        logging.error('Error fetching data or no data returned.')

if __name__ == "__main__":
    with open('config_testnet.json') as f:
        config = json.load(f)

    db_conn = init_db_connection(config)
    cursor = db_conn.cursor()
    create_table(cursor)

    url = config['api_url']
    network = config['network']
    result = get_latest_sui_system_state(url)

    if result:
        active_validators = result.get('result', {}).get('activeValidators', [])

        for validator in active_validators:
            exchange_rates_id = validator.get('exchangeRatesId')
            suiAddress = validator.get('suiAddress')
            pool_id = validator.get('stakingPoolId')
            active = True

            if exchange_rates_id:
                epochs = get_dynamic_fields_paginated(url, exchange_rates_id)

                if epochs:
                    db_epochs = fetch_epochs(cursor, exchange_rates_id)  # Fetch epochs from the database
                    missing_epochs = list(set(epochs) - set(db_epochs))  # Find the missing epochs
                    missing_epochs.sort()  # Sort the missing epochs

                    logging.info(f'ExchangeRatesId: {exchange_rates_id}, Epochs: {len(missing_epochs)}')

                    # Send request for each epoch
                    for epoch in missing_epochs:
                        dynamic_field_object_result = get_dynamic_field_object(url, exchange_rates_id, epoch)

                        if dynamic_field_object_result:
                            pool_token_amount = dynamic_field_object_result.get('result', {}).get('data', {}).get('content', {}).get('fields', {}).get('value', {}).get('fields', {}).get('pool_token_amount')
                            sui_amount = dynamic_field_object_result.get('result', {}).get('data', {}).get('content', {}).get('fields', {}).get('value', {}).get('fields', {}).get('sui_amount')

                            data_to_insert = (exchange_rates_id, network, suiAddress, pool_id, active, epoch, pool_token_amount, sui_amount)
                            insert_into_table(cursor, data_to_insert)
                            db_conn.commit()  # Commit the transaction
                            logging.info(f'Epoch: {epoch}, PoolTokenAmount: {pool_token_amount}, SuiAmount: {sui_amount}')

                        time.sleep(0.5) 
                else:
                    logging.info(f'Unable to get dynamic fields for exchangeRatesId {exchange_rates_id}')
    else:
        logging.info('Unable to get data.')
