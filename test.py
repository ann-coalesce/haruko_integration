from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd, logging, db_utils
from datetime import datetime, timezone
from haruko_utils import HarukoAPI


MAX_WORKERS = 5   # tune; 4-8 is typical for I/O work

API_CREDENTIALS = [
    # # {"pm": "farbfoxtrot_btc", "account_id": "130"},
    # # {"pm": "opttangopapa_btc", "account_id": "145"},
    # # {"pm": "optalphadelta_btc", "account_id": "149"},  
    # # {"pm": "ctauniformcharlie", "account_id": "140"},  
    # # {"pm": "ctapapa", "account_id": "141"},  
    # # {"pm": "ctaalphapapa", "account_id": "144"},  
    # {"pm": "cta_alphamike", "account_id": "133"},  
    # {"pm": "ctabravowhiskey", "account_id": "136"},  
    # {"pm": "ctabravowhiskey2", "account_id": "152"},  
    # {"pm": "bravowhiskey_btc", "account_id": "153"},  
    # {"pm": "ctaalphazulu", "account_id": "179"},  
    # {"pm": "ctaalphanovember", "account_id": "180"},  
    # # {"pm": "ctaromeolima", "account_id": "181"},  
    # # {"pm": "farbvictorcharlie_bybit01_btc", "account_id": "177"},
    # # {"pm": "farbvictorcharlie_bybit02_btc", "account_id": "178"},
    # # {"pm": "farbvictorcharlie_bitget01_btc", "account_id": "183"},
    # # {"pm": "farbvictorcharlie_bitget02_btc", "account_id": "186"},
    # # {"pm": "farbvictorcharlie_binance01_btc", "account_id": "184"},
    # # {"pm": "farbvictorcharlie_binance02_btc", "account_id": "185"},
    # # {"pm": "farbvictorcharlie_okx01_btc", "account_id": "187"},
    # # {"pm": "farbvictorcharlie_okx02_btc", "account_id": "188"},
    # {"pm": "arbtangojuliett", "account_id": "195"},
    # {"pm": "ctauniform", "account_id": "196"},
    # {"pm": "ctabravo", "account_id": "198"},
    # {"pm": "bellwetherholding", "account_id": "199"},
    # {"pm": "arbvictor", "account_id": "201"},
    # {"pm": "ctaalphanovemberalpha", "account_id": "202"},
    # {"pm": "coalesce", "account_id": "203"},
    # {"pm": "testsierrayankee", "account_id": "205"},
    # {"pm": "mljuliettzulu", "account_id": "207"},
    # {"pm": "testkilonovember", "account_id": "208"},
    # {"pm": "farbtangoromeo", "account_id": "209"},
    # {"pm": "testnovember", "account_id": "210"},
    {"pm": "cpas", "account_id": "50"},
    {"pm": "farbromeoalpha", "account_id": "172"},
    # {"pm": "deribit_master", "account_id": "20"},
]

def fetch_haruko_balance(account_id: str):
    """Fetch margin balance data from Haruko for a specific account"""
    api_client = HarukoAPI()
    result = api_client.get_balance(accountId=account_id)
    # print(json.dumps(result, indent=3))
    return result

def parse_haruko_margin_data(balance_data: dict, pm_name: str, timestamp: datetime):
    try:
        margin_list = balance_data['result']['margin']
        df = pd.DataFrame(margin_list)
        df = df[['key', 'marginBalance', 'initialMargin', 'maintenanceMargin']]
        df[['marginBalance', 'initialMargin', 'maintenanceMargin']] = df[['marginBalance', 'initialMargin', 'maintenanceMargin']].astype(float)
        df = df[df['marginBalance'] != 0]
        df.rename(columns={
            'key': 'currency',
            'marginBalance': 'collateral',
            'initialMargin': 'total_im',
            'maintenanceMargin': 'total_mm'
        }, inplace=True)
        df['timestamp'] = timestamp
        df['pm'] = pm_name
        return df
    except Exception as e:
        logging.error(f"Failed to parse Haruko margin data for {pm_name}: {e}")
        return None


def fetch_and_parse(cred, timestamp):
    try:
        raw = fetch_haruko_balance(cred["account_id"])
        return parse_haruko_margin_data(raw, cred["pm"], timestamp)
    except Exception as e:
        logging.error(f"{cred['pm']} failed: {e}")
        return None


# def main():
#     curr = datetime.now(timezone.utc).replace(second=0, microsecond=0)
#     dfs = []

#     with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
#         futures = {pool.submit(fetch_and_parse, c, curr): c for c in API_CREDENTIALS}
#         for fut in as_completed(futures):
#             df = fut.result()
#             if df is not None and not df.empty:
#                 dfs.append(df)

#     if dfs:
#         final_df = pd.concat(dfs, ignore_index=True)
#         db_utils.df_to_table("margin_risk_data", final_df)
#         print(final_df)
#     else:
#         print("No data collected")


# if __name__ == "__main__":
#     main()

def main():
    start_ts = datetime.now(timezone.utc)
    logging.info(f"Program started at {start_ts.isoformat()}")

    try:
        curr = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        dfs = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_and_parse, c, curr): c for c in API_CREDENTIALS}
            for fut in as_completed(futures):
                df = fut.result()
                if df is not None and not df.empty:
                    dfs.append(df)

        if dfs:
            final_df = pd.concat(dfs, ignore_index=True)
            db_utils.df_to_table("margin_risk_data", final_df)
            print(final_df)
        else:
            print("No data collected")

    finally:
        end_ts = datetime.now(timezone.utc)
        elapsed_s = (end_ts - start_ts).total_seconds()
        logging.info(f"Program finished at {end_ts.isoformat()} (elapsed: {elapsed_s:.2f}s)")
        print(f"START:  {start_ts.isoformat()}")
        print(f"FINISH: {end_ts.isoformat()}")
        print(f"ELAPSED: {elapsed_s:.2f}s")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ %(levelname)s %(message)s",
    )
    main()
