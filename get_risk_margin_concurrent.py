from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd, logging, db_utils
from datetime import datetime, timezone
from haruko_utils import HarukoAPI


MAX_WORKERS = 5   # tune; 4-8 is typical for I/O work


def load_credentials():
    df = db_utils.get_db_table(
        "SELECT pm, haruko_id FROM pm_mapping WHERE active = true AND haruko_id IS NOT NULL ORDER BY haruko_id"
    )
    return [{"pm": row.pm, "account_id": str(int(row.haruko_id))} for row in df.itertuples()]

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
        credentials = load_credentials()
        logging.info(f"Loaded {len(credentials)} active accounts from pm_mapping")
        curr = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        dfs = []

        pms_with_data = set()
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_and_parse, c, curr): c for c in credentials}
            for fut in as_completed(futures):
                df = fut.result()
                if df is not None and not df.empty:
                    dfs.append(df)
                    pms_with_data.add(df["pm"].iloc[0])

        empty_pms = [c["pm"] for c in credentials if c["pm"] not in pms_with_data]
        if empty_pms:
            logging.warning(f"No margin data for ({len(empty_pms)}): {', '.join(sorted(empty_pms))}")

        if dfs:
            final_df = pd.concat(dfs, ignore_index=True)
            logging.info(f"Writing {len(final_df)} rows for {len(pms_with_data)} PMs")
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
