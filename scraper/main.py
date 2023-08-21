#!/usr/bin/env python3
import json
import time
import logging
import os
from datetime import datetime, timedelta
import schedule
import requests
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from requests.exceptions import ConnectionError, Timeout, RequestException
from contextlib import contextmanager

current_epoch = None

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S',
    handlers=[logging.StreamHandler()]
)

@contextmanager
def get_cursor(pool):
    conn = pool.get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def create_database(cursor, mysql_database):
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_database}")

def create_table_system_state(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_state (
            epoch TEXT,
            network TEXT,
            sui_address TEXT,
            protocol_pubkey_bytes TEXT,
            network_pubkey_bytes TEXT,
            worker_pubkey_bytes TEXT,
            name TEXT,
            description TEXT,
            image_url TEXT,
            project_url TEXT,
            net_address TEXT,
            p2p_address TEXT,
            primary_address TEXT,
            worker_address TEXT,
            voting_power TEXT,
            gas_price TEXT,
            commission_rate TEXT,
            stake TEXT,
            apy DOUBLE,
            rate_change DECIMAL(18, 15) NULL
        )
    ''')

def create_table_validator_data(cursor):
    cursor.execute('''
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
    ''')

def insert_into_table(cursor, data):
    query = """
         INSERT IGNORE INTO validators_data (exchange_rates_id, network, suiAddress, pool_id, active, epoch, pool_token_amount, sui_amount)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, data)

def fetch_epoch_db(cursor, exchange_rates_id):
    query = """
        SELECT epoch FROM validators_data WHERE exchange_rates_id = %s
    """
    cursor.execute(query, (exchange_rates_id,))
    rows = cursor.fetchall()
    return [row[0] for row in rows]  # Extract the epochs from the rows


def make_request(url, headers, data, timeout=30, max_retries=3, backoff_factor=1.5):
    for i in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=timeout)
            response.raise_for_status()
            return response
        except (ConnectionError, Timeout) as e:
            logging.error(f"Connection error or timeout: {e}. Retrying in {backoff_factor ** i} seconds.")
            time.sleep(backoff_factor ** i)
        except RequestException as e:
            logging.error(f"Specific error encountered: {e}. Exiting.")
            return None
        except Exception as e:
            logging.error(f"Unexpected error encountered: {e}. Retrying in {backoff_factor ** i} seconds.")
            time.sleep(backoff_factor ** i)
    return None



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

def get_history_apy(url, network, pool):
    logging.info(f'Fetching history APY for {network} {pool}...')
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
                    # Using the connection pool for database operations
                    with pool.get_connection() as conn:
                        cursor = conn.cursor()

                        db_epochs = fetch_epoch_db(cursor, exchange_rates_id)  # Fetch epochs from the database
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
                                conn.commit()  # Commit the transaction
                                logging.info(f'Epoch: {epoch}, PoolTokenAmount: {pool_token_amount}, SuiAmount: {sui_amount}')

                            # time.sleep(0.5)

                        cursor.close()
                else:
                    logging.info(f'Unable to get dynamic fields for exchangeRatesId {exchange_rates_id}')
    else:
        logging.info('Unable to get data.')



def request_epoch(api_url):
    data = get_latest_sui_system_state(api_url)
    epoch = data['result']['epoch']
    return epoch

def store_data_in_database(json_data, network, pool):
    epoch = json_data['result']['epoch']
    active_validators = json_data['result']['activeValidators']

    try:
        mydb = pool.get_connection()
        cursor = mydb.cursor()
        for validator in active_validators:
            sui_address = validator['suiAddress']
            protocol_pubkey_bytes = validator['protocolPubkeyBytes']
            network_pubkey_bytes = validator['networkPubkeyBytes']
            worker_pubkey_bytes = validator['workerPubkeyBytes']
            name = validator['name']
            description = validator['description']
            image_url = validator['imageUrl']
            project_url = validator['projectUrl']
            net_address = validator['netAddress']
            p2p_address = validator['p2pAddress']
            primary_address = validator['primaryAddress']
            worker_address = validator['workerAddress']
            voting_power = validator['votingPower']
            gas_price = validator['gasPrice']
            commission_rate = validator['commissionRate']
            stake = validator['stakingPoolSuiBalance']

            query = """
            INSERT INTO system_state (
                epoch, network, sui_address, protocol_pubkey_bytes, network_pubkey_bytes,
                worker_pubkey_bytes, name, description, image_url, project_url, net_address,
                p2p_address, primary_address, worker_address, voting_power, gas_price,
                commission_rate, stake, apy
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
            """
            values = (
                epoch, network, sui_address, protocol_pubkey_bytes, network_pubkey_bytes,
                worker_pubkey_bytes, name, description, image_url, project_url, net_address,
                p2p_address, primary_address, worker_address, voting_power, gas_price,
                commission_rate, stake
            )
            cursor.execute(query, values)
            mydb.commit()  # Explicitly committing the transaction
            logging.info(f"Data for {epoch} for validator {name} - {sui_address} - stored in the database successfully!")

        cursor.close()
        mydb.close()
    except Exception as e:
        logging.error(f"Error while storing data: {e}")


def update_apy(api_url, network, epoch, pool):
    headers = {'Content-Type': 'application/json'}
    data = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'suix_getValidatorsApy',
        'params': []
    }
    response = requests.post(api_url, headers=headers, json=data, timeout=30)
    json_data = response.json()

    try:
        mydb = pool.get_connection()
        cursor = mydb.cursor()

        apys = json_data['result']['apys']
        for apy_data in apys:
            address = apy_data['address']
            apy = apy_data['apy']
            cursor.execute('''UPDATE system_state SET apy = %s WHERE sui_address = %s and network = %s and epoch = %s''', (apy, address, network,epoch))
            mydb.commit()

        cursor.close()
        mydb.close()
        logging.info("APY values updated in the database successfully!")
        logging.info(40 * "-")
    except mysql.connector.Error as err:
        logging.error(f"Error updating row: {err}")


def update_rate_change(network, pool):
    logging.info("Scraping rate change...")
    try:
        mydb = pool.get_connection()
        cursor = mydb.cursor()
        # Get distinct epochs with NULL rate_change for the specified network
        cursor.execute("SELECT DISTINCT epoch FROM system_state WHERE network = %s AND rate_change IS NULL", (network,))
        epochs_to_update = [row[0] for row in cursor.fetchall()]

        for epoch in epochs_to_update:
            # Fetch previous epoch data
            cursor.execute("SELECT epoch, sui_address, apy FROM system_state WHERE network = %s AND epoch = %s", (network, str(int(epoch) - 1)))
            previous_data = {row[1]: row[2] for row in cursor.fetchall()}

            # Fetch current epoch data
            cursor.execute("SELECT sui_address, apy FROM system_state WHERE network = %s AND epoch = %s", (network, epoch))
            for row in cursor.fetchall():
                address, apy = row
                prev_apy = previous_data.get(address, apy)
                rate_change = apy - prev_apy # Calculates the change in rate, can be positive or negative

                logging.info(f"Rate change for epoch {epoch} for validator {address} is {rate_change}")

                # Update the rate_change
                cursor.execute("UPDATE system_state SET rate_change = %s WHERE sui_address = %s AND network = %s AND epoch = %s",
                               (rate_change, address, network, epoch))
                mydb.commit()

            logging.info(f"Rate change for epoch {epoch} updated in the database successfully!")
        else:
            logging.info("No epochs to update rate change for")
        cursor.close()
        mydb.close()
        logging.info(40 * "-")
    except Exception as e:
        logging.error(f"Error while storing data: {e}")


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


def check_and_run_job(api_url, network, pool):
    current_epoch = request_epoch(api_url)
    logging.info("Current epoch: %s", current_epoch)

    with get_cursor(pool) as cursor:
        cursor.execute("SELECT epoch FROM system_state WHERE network = %s ORDER BY CAST(epoch AS UNSIGNED) DESC LIMIT 1;", (network,))
        result = cursor.fetchone()

        if result:
            logging.info("Last epoch in the database: %s", result[0])
        else:
            logging.info("No epoch data found in the database.")

        if result is None or current_epoch != result[0]:
            logging.info("No data found for %s. Running job to fetch and store data...", current_epoch)
            json_data = get_latest_sui_system_state(api_url)
            store_data_in_database(json_data, network, pool)
            update_apy(api_url, network, current_epoch, pool)
        else:
            logging.info("Data already exists in the database. Skipping job")
            logging.info("Waiting until epoch changes to run job again...")
            logging.info(40 * "-")


def calculate_time_left(epoch_start_timestamp_ms, epoch_duration_ms):
    current_timestamp_ms = int(time.time() * 1000)
    epoch_start_timestamp = int(epoch_start_timestamp_ms)
    epoch_duration = int(epoch_duration_ms)
    time_left = epoch_start_timestamp + epoch_duration - current_timestamp_ms
    minutes_left = int(time_left / (1000 * 60))
    return minutes_left


def print_time_left(api_url):
    json_data = get_latest_sui_system_state(api_url)
    epoch_start_timestamp_ms = json_data['result']['epochStartTimestampMs']
    epoch_duration_ms = json_data['result']['epochDurationMs']
    current_epoch = json_data['result']['epoch']
    next_epoch = int(current_epoch) + 1

    # Convert epoch start timestamp to local time
    epoch_start_timestamp = datetime.fromtimestamp(int(epoch_start_timestamp_ms) / 1000)

    # Calculate the end timestamp of the current epoch
    epoch_end_timestamp = epoch_start_timestamp + timedelta(milliseconds=int(epoch_duration_ms))

    # Calculate the time left until the next epoch
    current_time = datetime.now()
    time_left = epoch_end_timestamp - current_time
    minutes_left = int(time_left.total_seconds() / 60)

    # Calculate the datetime of the next epoch
    next_epoch_datetime = current_time + time_left

    # Format the next epoch datetime for display
    next_epoch_formatted = next_epoch_datetime.strftime('%Y-%m-%d %H:%M:%S')

    logging.info("Time left on epoch %s until next epoch: %s minutes", current_epoch, minutes_left)
    logging.info("Epoch %s will occur at: %s", next_epoch, next_epoch_formatted)
    logging.info(40 * '-')


def run_jobs(api_url, network, pool):
    global current_epoch
    # Check the current epoch
    new_epoch = request_epoch(api_url)
    # If it's a new epoch, run the tasks and update the global variable
    if current_epoch is None or new_epoch != current_epoch:
        current_epoch = new_epoch
        check_and_run_job(api_url, network, pool)
        time.sleep(10)
        update_rate_change(network, pool)
        time.sleep(10)
        get_history_apy(api_url, network, pool)

def main():
    logging.info(40 * '-')
    logging.info('SUI Data collector')
    logging.info(40 * '-')

    config_file_path = os.getenv('CONFIG_FILE', 'config.json')
    with open(config_file_path) as config_file:
        config = json.load(config_file)

    mysql_username = config['mysql_username']
    mysql_password = config['mysql_password']
    mysql_database = config['mysql_database']
    mysql_host = config['mysql_host']
    api_url = config['api_url']
    network = config['network']

    # Database Connection Pooling
    dbconfig = {
        "host": mysql_host,
        "user": mysql_username,
        "password": mysql_password,
        "database": mysql_database
    }
    pool = MySQLConnectionPool(pool_name="sui", pool_size=5, **dbconfig)

    with get_cursor(pool) as cursor:
        create_database(cursor, mysql_database)
        create_table_system_state(cursor)
        create_table_validator_data(cursor)

    run_jobs(api_url, network, pool)

    # Schedule the jobs
    schedule.every(10).minutes.do(run_jobs, api_url=api_url, network=network, pool=pool)
    schedule.every(15).minutes.do(print_time_left, api_url=api_url)

    while True:
        schedule.run_pending()
        time.sleep(1)  # Sleep for 1 second

if __name__ == '__main__':
    main()
