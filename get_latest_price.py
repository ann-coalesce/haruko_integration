import os
import logging
import credentials

from binance_sdk_spot.spot import Spot, ConfigurationRestAPI, SPOT_REST_API_PROD_URL
from binance_sdk_spot.rest_api.models import KlinesIntervalEnum

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create configuration for the REST API
configuration_rest_api = ConfigurationRestAPI(
    api_key=credentials.API_KEY,
    api_secret=credentials.API_SECRET,
    base_path=SPOT_REST_API_PROD_URL,
    timeout=5000
)

# Initialize Spot client
client = Spot(config_rest_api=configuration_rest_api)


def latest_price(symbol='BTCUSDT'):
    try:
        response = client.rest_api.ticker_price(symbol=symbol)

        rate_limits = response.rate_limits
        logging.info(f"ticker_price() rate limits: {rate_limits}")

        data = response.data()
        price = float(data.actual_instance.price)
        print(f'price: {price}')
        logging.info(f"ticker_price() response: {data}")
        return price
    except Exception as e:
        logging.error(f"ticker_price() error: {e}")
        return -1

if __name__ == "__main__":
    latest_price()