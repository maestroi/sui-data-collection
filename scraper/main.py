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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S',
    handlers=[logging.StreamHandler()]
)


config_file = os.getenv('CONFIG_FILE', 'config.json')
with open(config_file) as config_file:
    config = json.load(config_file)

mysql_username = config['mysql_username']
mysql_password = config['mysql_password']
mysql_database = config['mysql_database']
mysql_host = config['mysql_host']
api_url = config['api_url']
network = config['network']

# Create a connection pool outside of the function
dbconfig = {
    "host": mysql_host,
    "user": mysql_username,
    "password": mysql_password,
    "database": mysql_database
}
pool = MySQLConnectionPool(pool_name="sui", pool_size=5, **dbconfig)

def request_data(api_url):
    headers = {'Content-Type': 'application/json'}
    data = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'suix_getLatestSuiSystemState',
        'params': []
    }
    response = requests.post(api_url, headers=headers, json=data, timeout=30)
    return response.json()

def request_epoch(api_url):
    data = request_data(api_url)
    epoch = data['result']['epoch']
    return epoch

def store_data_in_database(json_data, network):
    epoch = json_data['result']['epoch']
    active_validators = json_data['result']['activeValidators']
    try:
        mydb = pool.get_connection()
        cursor = mydb.cursor()

        for validator in active_validators:
            sui_address = validator['suiAddress']
            network = config['network']
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
            mydb.commit()
            logging.info(f"Data for {epoch} for validator {name} - {sui_address} - stored in the database successfully!")

        cursor.close()
        mydb.close()
        logging.info("Data stored in the database successfully!")
    except mysql.connector.Error as err:
        logging.error(f"Error updating row: {err}")


def update_apy(api_url, network, epoch):
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
    except mysql.connector.Error as err:
        logging.error(f"Error updating row: {err}")

def create_database(network):
    try:
        mydb = pool.get_connection()
        cursor = mydb.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_database}")
        cursor.execute('''CREATE TABLE IF NOT EXISTS system_state (
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
                        )''')

        cursor.close()
        mydb.close()
        logging.info("Database created successfully!")
    except mysql.connector.Error as err:
        logging.error(f"Error updating row: {err}")

def update_rate_change(network):
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

        cursor.close()
        mydb.close()
    except mysql.connector.Error as err:
        logging.error(f"Error updating row: {err}")


def check_and_run_job(api_url, network):
    current_epoch = request_epoch(api_url)
    logging.info("Current epoch: %s", current_epoch)

    try:
        mydb = pool.get_connection()
        cursor = mydb.cursor()

        cursor.execute("SELECT epoch FROM system_state WHERE network = %s ORDER BY CAST(epoch AS UNSIGNED) DESC LIMIT 1;", (network,))
        result = cursor.fetchone()

        logging.info("Last epoch in the database: %s", result[0])

        if result is None or current_epoch != result[0]:
            logging.info("No data found for %s. Running job to fetch and store data...", current_epoch)
            json_data = request_data(api_url)
            store_data_in_database(json_data, network)
            update_apy(api_url, network, current_epoch)
        else:
            logging.info("Data already exists in the database. Skipping job")
            logging.info("Waiting until epoch changes to run job again...")
        cursor.close()
        mydb.close()
    except mysql.connector.Error as err:
        logging.error(f"Error selecting row: {err}")

def calculate_time_left(epoch_start_timestamp_ms, epoch_duration_ms):
    current_timestamp_ms = int(time.time() * 1000)
    epoch_start_timestamp = int(epoch_start_timestamp_ms)
    epoch_duration = int(epoch_duration_ms)
    time_left = epoch_start_timestamp + epoch_duration - current_timestamp_ms
    minutes_left = int(time_left / (1000 * 60))
    return minutes_left

def print_time_left(api_url):
    json_data = request_data(api_url)
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

def main():
    logging.info(40 * '-')
    logging.info('SUI Data collector')
    logging.info(40 * '-')

    # Create the database and tables if they don't exist
    create_database(network)

    # Check if the latest epoch is already in the database
    check_and_run_job(api_url, network)

    # Calculate and print time left until next epoch every 1 minute
    schedule.every(10).minutes.do(print_time_left, api_url=api_url)

    # Schedule the job to run every 60 minutes
    schedule.every(5).minutes.do(update_rate_change, network=network)

    # Run the scheduled tasks
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()
