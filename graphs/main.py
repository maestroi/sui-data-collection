#!/usr/bin/env python3
import requests
import pandas as pd
import matplotlib.pyplot as plt
import argparse

def get_data(network):
    url = f"https://api-sui.cryptosnapshotservice.com/api/data?network={network}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return None

def filter_data(data, name):
    return [item for item in data if item.get('name') == name]

def generate_graphs(data, network):
    # Convert the data to a DataFrame for easier manipulation
    df = pd.DataFrame(data)

    # Plot commission_rate over epoch number
    plt.figure(figsize=(12, 6))
    plt.plot(df['epoch'], df['commission_rate'].astype(float), marker='o', linestyle='-', label='Commission Rate')
    plt.title('Commission Rate over Epoch Number')
    plt.xlabel('Epoch Number')
    plt.ylabel('Commission Rate')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'{network}_commission_rate.png')
    plt.close()

    # Plot gas_price over epoch number
    plt.figure(figsize=(12, 6))
    plt.plot(df['epoch'], df['gas_price'].astype(int), marker='o', linestyle='-', label='Gas Price')
    plt.title('Gas Price over Epoch Number')
    plt.xlabel('Epoch Number')
    plt.ylabel('Gas Price')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'{network}_gas_price.png')
    plt.close()

    # Plot apy over epoch number
    plt.figure(figsize=(12, 6))
    plt.plot(df['epoch'], df['apy'].astype(float), marker='o', linestyle='-', label='APY')
    plt.title('APY over Epoch Number')
    plt.xlabel('Epoch Number')
    plt.ylabel('APY')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'{network}_apy.png')
    plt.close()

    # Plot stake over epoch number
    plt.figure(figsize=(12, 6))
    plt.plot(df['epoch'], df['stake'].astype(int), marker='o', linestyle='-', label='Stake')
    plt.title('Stake over Epoch Number')
    plt.xlabel('Epoch Number')
    plt.ylabel('Stake')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'{network}_stake.png')
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate graphs for Blockdaemon data.')
    parser.add_argument('network', choices=['mainnet', 'testnet'], help='Specify the network (mainnet or testnet)')
    args = parser.parse_args()

    # Make the API request and get the data for the specified network
    data = get_data(args.network)
    if data:
        # Filter data for the desired name (e.g., "Blockdaemon")
        name = "Blockdaemon"
        filtered_data = filter_data(data, name)
        if filtered_data:
            generate_graphs(filtered_data, args.network)
        else:
            print(f"No data found for {name}.")
