#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging
import json
import uvicorn
import os
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

# Create a FastAPI app instance
app = FastAPI()

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

# GET endpoint to retrieve system states filtered by network
@app.get("/api/data")
async def get_system_states(network: str = 'mainnet', epoch: int = None):
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
                "apy": result[18]
            }
            system_state = SystemState(**system_state_dict)
            system_states.append(system_state)
        return system_states
    except mysql.connector.Error as err:
        logging.error(f"Error fetching system states: {err}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        cursor.close()
        mydb.close()

# Run the FastAPI application
if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)
