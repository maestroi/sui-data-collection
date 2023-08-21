#!/usr/bin/env python3
import requests
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s — %(message)s',
                    datefmt='%Y-%m-%d_%H:%M:%S',
                    handlers=[logging.StreamHandler()])

def fetch_exchange_rates():
    url = "https://api.sui-data.com/api/v1/token-exchange-rate?sui_address=0x58baf5de9454ce6e6d17ebcf7d31513d700d012f304b16ef02e4a5b187cd9c13&network=testnet"
    response = requests.get(url)
    response.raise_for_status()  # will raise an exception if the HTTP request returned an error status code
    return response.json()

def calculate_apy(rate_e, rate_e_1):
    er_e = rate_e["PoolTokenExchangeRate"]["pool_token_amount"] / rate_e["PoolTokenExchangeRate"]["sui_amount"]
    er_e_1 = rate_e_1["PoolTokenExchangeRate"]["pool_token_amount"] / rate_e_1["PoolTokenExchangeRate"]["sui_amount"]
    return (er_e_1 / er_e) ** 365 - 1.0

def main():
    data = fetch_exchange_rates()

    # Get all unique epochs except epoch 0, and sort them in descending order
    unique_epochs = sorted(set(rate["epoch"] for rate in data["rates"] if rate["epoch"] != 0), reverse=False)

    # Sorting the rates by epoch in descending order
    sorted_rates = sorted(data["rates"], key=lambda x: x["epoch"], reverse=False)

    stake_subsidy_start_epoch = 1

    for epoch in unique_epochs:
        exchange_rates = [
            rate for rate in sorted_rates
            if stake_subsidy_start_epoch <= rate["epoch"] <= epoch and (1.0 / (rate["PoolTokenExchangeRate"]["pool_token_amount"] / rate["PoolTokenExchangeRate"]["sui_amount"])) < 1.2
        ][-31:]

        if len(exchange_rates) >= 2:
            er_e = exchange_rates[1:]
            er_e_1 = exchange_rates[:-1]
            average_apy = sum(map(calculate_apy, er_e, er_e_1)) / len(er_e)
        else:
            average_apy = 0.0

        logging.info(f"Epoch: {epoch}, Average APY: {average_apy:.8f}%")


if __name__ == "__main__":
    main()
