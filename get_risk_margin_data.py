
import pandas as pd
from datetime import datetime, timezone
import logging
from haruko_utils import HarukoAPI
import credentials
import db_utils

# Configuration: Add as many as needed
API_CREDENTIALS = [
    # {"pm": "farbfoxtrot_btc", "account_id": "130"},
    {"pm": "opttangopapa_btc", "account_id": "145"},
    {"pm": "optalphadelta_btc", "account_id": "149"},  
    {"pm": "ctauniformcharlie", "account_id": "140"},  
    {"pm": "ctapapa", "account_id": "141"},  
    {"pm": "ctaalphapapa", "account_id": "144"},  
    {"pm": "cta_alphamike", "account_id": "133"},  
    {"pm": "ctabravowhiskey", "account_id": "136"},  
    {"pm": "ctabravowhiskey2", "account_id": "152"},  
    {"pm": "bravowhiskey_btc", "account_id": "153"},
]

def fetch_haruko_balance(account_id: str):
    """Fetch margin balance data from Haruko for a specific account"""
    api_client = HarukoAPI()
    result = api_client.get_balance(accountId=account_id)
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

def main():
    all_dfs = []
    curr = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    for cred in API_CREDENTIALS:
        try:
            print(f"Processing account: {cred['pm']}")
            res = fetch_haruko_balance(cred['account_id'])

            parsed_df = parse_haruko_margin_data(res, pm_name=cred['pm'], timestamp=curr)
            if parsed_df is not None and not parsed_df.empty:
                all_dfs.append(parsed_df)
            else:
                print(f"No margin data parsed for {cred['pm']}")

        except Exception as e:
            print(f"Error processing {cred['pm']}: {str(e)}")
            logging.error(f"Error processing {cred['pm']}: {str(e)}")

    # Combine and save
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        db_utils.df_to_table(table_name='margin_risk_data', df=final_df)
        print("\nCombined DataFrame:")
        print(final_df)
    else:
        print("No data collected")

if __name__ == "__main__":
    main()
