import logging
from haruko_utils import HarukoAPI
from datetime import datetime, timezone, timedelta
import pandas as pd
import db_utils
import sys

# Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# StreamHandler for stdout (captured by systemd)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(stream_handler)

pm_mapping = [
    # {'haruko_id': 156, 'pm': 'farbromeocharliebybit_btc'},
    # {'haruko_id': 157, 'pm': 'farbromeocharliegate_btc'},
    {'haruko_id': 177, 'pm': 'farbvictorcharlie_bybit01_btc'},
    {'haruko_id': 178, 'pm': 'farbvictorcharlie_bybit02_btc'},
    {'haruko_id': 183, 'pm': 'farbvictorcharlie_bitget01_btc'},
    {'haruko_id': 186, 'pm': 'farbvictorcharlie_bitget02_btc'},
    {'haruko_id': 184, 'pm': 'farbvictorcharlie_binance01_btc'},
    {'haruko_id': 185, 'pm': 'farbvictorcharlie_binance02_btc'},
    {'haruko_id': 187, 'pm': 'farbvictorcharlie_okx01_btc'},
    {'haruko_id': 188, 'pm': 'farbvictorcharlie_okx02_btc'},
]
pm_mapping_df = pd.DataFrame(pm_mapping)

def main():
    logger.info("Starting transfer data processing")
    
    try:
        api_client = HarukoAPI()
        accountid_list = ",".join(str(acc_id) for acc_id in pm_mapping_df['haruko_id'])
        start_ts = int((datetime.now(tz=timezone.utc) - timedelta(days=3)).timestamp()) * 1000
        
        logger.info(f"Fetching transfers for accounts: {accountid_list}")
        res = api_client.get_aggregate_transfers(accountIds=accountid_list, startTs=start_ts)

        df = pd.DataFrame(res['result']['entries'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, unit='ms')
        df.rename(columns={'venueAccountId':'haruko_id',  'asset':'symbol'}, inplace=True)
        df = df[['timestamp', 'symbol', 'size', 'haruko_id']]
        df_merged = pd.merge(df, pm_mapping_df, on='haruko_id', how='left')
        
        logger.info(f"Successfully processed {len(df_merged)} transfer records")
        print(df_merged)
    except Exception as e:
        logger.error(f"API/Processing Error: {e}")
        
    try:
        db_utils.insert_transfer_events_on_conflict(df=df_merged)
        logger.info("Successfully saved to database")
    except Exception as e:
        logger.error(f"Database Error: {e}")

if __name__ == "__main__":
    main()