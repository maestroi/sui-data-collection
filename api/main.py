#!/usr/bin/env python3
# Standard library imports
import json
import logging
import os

# Third-party imports
from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.responses import RedirectResponse
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
import uvicorn
from typing import List

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
api_route = '/api/v1/'

# Create a connection pool outside of the function
dbconfig = {
    "host": mysql_host,
    "user": mysql_username,
    "password": mysql_password,
    "database": mysql_database
}
pool = MySQLConnectionPool(pool_name="sui", pool_size=5, **dbconfig)

# Create a FastAPI app instance
app = FastAPI(docs_url="/docs")

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data model for the system state
class SystemState(BaseModel):
    epoch: int
    network: str
    sui_address: str
    protocol_pubkey_bytes: str
    network_pubkey_bytes: str
    worker_pubkey_bytes: str
    name: str
    description: str
    image_url: str
    project_url: str
    net_address: str
    p2p_address: str
    primary_address: str
    worker_address: str
    voting_power: str
    gas_price: str
    commission_rate: str
    stake: str
    apy: float
    rate_change: float

# Model for exchange rate
class ExchangeRate(BaseModel):
    suiAddress: str
    pool_id: str
    active: bool
    rates: List[dict]

def calculate_apy(rate_e, rate_e_1):
    er_e = rate_e["PoolTokenExchangeRate"]["pool_token_amount"] / rate_e["PoolTokenExchangeRate"]["sui_amount"]
    er_e_1 = rate_e_1["PoolTokenExchangeRate"]["pool_token_amount"] / rate_e_1["PoolTokenExchangeRate"]["sui_amount"]
    return (er_e / er_e_1) ** 365 - 1.0

def get_sui_address(name: str, network: str, table_name: str = "system_state"):
    connection = pool.get_connection()
    cursor = connection.cursor()

    try:
        query = f"SELECT sui_address FROM {table_name}  WHERE name = %s AND network = %s LIMIT 1"
        cursor.execute(query, (name, network))
        records = cursor.fetchall()
        sui_address = records[0]
        return sui_address[0]

    except mysql.connector.Error as err:
        logging.error(f"Error: {err}")
        raise

    finally:
        cursor.close()
        connection.close()

def get_apy_data(sui_address: str, network: str, table_name: str = "validators_data"):
    connection = pool.get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        query = f"SELECT * FROM {table_name} WHERE suiAddress = %s AND network = %s"
        cursor.execute(query, (sui_address, network))
        records = cursor.fetchall()

        if records is None or len(records) == 0:
            raise ValueError("Exchange rate not found")

        rate_list = []
        for record in records:
            rate_dict = {
                "epoch": record["epoch"],
                "PoolTokenExchangeRate": {
                    "sui_amount": record["sui_amount"],
                    "pool_token_amount": record["pool_token_amount"]
                }
            }
            rate_list.append(rate_dict)

        return {
            "suiAddress": sui_address,
            "pool_id": records[0]["pool_id"],
            "active": records[0]["active"],
            "rates": rate_list
        }

    except mysql.connector.Error as err:
        logging.error(f"Error: {err}")
        raise

    finally:
        cursor.close()
        connection.close()

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")

router = APIRouter()
# GET endpoint to retrieve system states filtered by network
@router.get(f"/historydata")
async def get_system_states(network: str = 'mainnet'):
    mydb = pool.get_connection()
    cursor = mydb.cursor()
    try:
        query = f"SELECT * FROM system_state WHERE network = '{network}';"
        cursor.execute(query)
        results = cursor.fetchall()
        system_states = []
        for result in results:
            system_state_dict = {
                "epoch": result[0],
                "network": result[1],
                "sui_address": result[2],
                "protocol_pubkey_bytes": result[3],
                "network_pubkey_bytes": result[4],
                "worker_pubkey_bytes": result[5],
                "name": result[6],
                "description": result[7],
                "image_url": result[8],
                "project_url": result[9],
                "net_address": result[10],
                "p2p_address": result[11],
                "primary_address": result[12],
                "worker_address": result[13],
                "voting_power": result[14],
                "gas_price": result[15],
                "commission_rate": result[16],
                "stake": result[17],
                "apy": result[18],
                "rate_change": result[19]
            }
            system_state = SystemState(**system_state_dict)
            system_states.append(system_state)
        return system_states
    except mysql.connector.Error as err:
        logging.error(f"Error fetching system states: {err}")
    finally:
        cursor.close()
        mydb.close()

@router.get("/rates")
async def get_rates(name: str = Query(...), network: str = Query(...)):
    try:
        sui_address = get_sui_address(name, network)
        logging.info(sui_address)
        # Use the get_apy_data function to get data
        data = get_apy_data(sui_address, network)
        rate_list = data["rates"]

        # Utilize the rate_list as in your previous script
        unique_epochs = sorted(set(rate["epoch"] for rate in rate_list if rate["epoch"] != 0), reverse=True)
        sorted_rates = sorted(rate_list, key=lambda x: x["epoch"], reverse=False)

        average_apy_list = []

       # logging.info(rate_list)

        stake_subsidy_start_epoch = 1

        unique_epochs_temp = [120]

        for unique_epoch in unique_epochs_temp:
            exchange_rates = [
                rate for rate in sorted_rates
                if rate["epoch"] <= unique_epoch and rate["epoch"] >= stake_subsidy_start_epoch and (1.0 / (rate["PoolTokenExchangeRate"]["pool_token_amount"] / rate["PoolTokenExchangeRate"]["sui_amount"])) < 1.2][-31:]

            if len(exchange_rates) >= 2:
                er_e = exchange_rates[1:]
                logging.info(er_e)
                logging.info("Exchange rate")
                er_e_1 = exchange_rates[:-1]

                logging.info(er_e_1)
                average_apy = sum(map(calculate_apy, er_e, er_e_1)) / len(er_e)
            else:
                average_apy = 0.0

            average_apy_list.append({
                "epoch": unique_epoch,
                "average_apy": average_apy
            })

        logging.info(50 * "-")
        logging.info(average_apy_list)

        return {
            "name": name,
            "suiAddress": sui_address,
            "average_apy": average_apy_list
        }

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/token-exchange-rate", response_model=ExchangeRate)
async def get_token_exchange_rate(sui_address: str = Query(...), network: str = Query(...)):
    try:
        return get_apy_data(sui_address, network)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/historydata/csv")
async def download_system_states(network: str = 'mainnet', names: List[str] = Query(None)):
    mydb = pool.get_connection()
    cursor = mydb.cursor()
    try:
        query = f"SELECT * FROM system_state WHERE network = '{network}'"
        if names:
            # Escape single quotes and join the names with commas
            escaped_names = "','".join(map(lambda x: x.replace("'", "''"), names))
            query += f" AND name IN ('{escaped_names}')"
        query += ";"

        cursor.execute(query)
        results = cursor.fetchall()

        # CSV column headers
        csv_columns = [
            "epoch", "network", "sui_address", "protocol_pubkey_bytes", "network_pubkey_bytes",
            "worker_pubkey_bytes", "name", "description", "image_url", "project_url", "net_address",
            "p2p_address", "primary_address", "worker_address", "voting_power", "gas_price",
            "commission_rate", "stake", "apy", "rate_change"
        ]

        # Create a list to store rows as dictionaries
        data = []
        for result in results:
            system_state_dict = {
                "epoch": result[0],
                "network": result[1],
                "sui_address": result[2],
                "protocol_pubkey_bytes": result[3],
                "network_pubkey_bytes": result[4],
                "worker_pubkey_bytes": result[5],
                "name": result[6],
                "description": result[7],
                "image_url": result[8],
                "project_url": result[9],
                "net_address": result[10],
                "p2p_address": result[11],
                "primary_address": result[12],
                "worker_address": result[13],
                "voting_power": result[14],
                "gas_price": result[15],
                "commission_rate": result[16],
                "stake": result[17],
                "apy": result[18],
                "rate_change": result[19]
            }
            data.append(system_state_dict)

        # Generate the CSV content
        def generate_csv():
            yield ",".join(csv_columns) + "\n"
            for item in data:
                yield ",".join(str(item[column]) for column in csv_columns) + "\n"

        return StreamingResponse(generate_csv(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="system_states.csv"'})

    except mysql.connector.Error as err:
        logging.error(f"Error fetching system states: {err}")
        raise HTTPException(status_code=500, detail="Database error")

    finally:
        cursor.close()
        mydb.close()

app.include_router(router, prefix="/api/v1")


# Run the FastAPI application
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
