import credentials
import requests
from datetime import datetime, timezone
import pandas as pd
import sheet_utils
import db_utils

def get_latest_price(venue='BINANCE', symbol='BTCUSDT'):
    base_url='https://co1.haruko.io'
    headers = {'Authorization': f'Bearer <{credentials.HARUKO_KEY}>', 'Content-Type': 'application/json'}
    endpoint = '/cefi/api/pricing/instruments/live'
    full_url = f"{base_url}{endpoint}"
    print('url',full_url)

    payload = {'venue':venue}
    response = requests.get(full_url, headers=headers, params=payload)
    res = response.json()

    price = None
    for instrument in res["result"]["instruments"]:
        if instrument["symbol"] == symbol:
            price = instrument["referencePrice"]
            break  # Stop searching once BTC is found

    print(f'price for {symbol} is {price}')
    return price

def get_trading_vol(account_ids, pm, start=None, end=None):
    base_url = 'https://co1.haruko.io'
    headers = {'Authorization': f'Bearer <{credentials.HARUKO_KEY}>', 'Content-Type': 'application/json'}
    endpoint = '/cefi/api/trades'
    full_url = f"{base_url}{endpoint}"
    print('url', full_url)

    # Get current day 00:00 unix timestamp if not provided
    if start is None:
        start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start = int(start_of_day.timestamp() * 1000)
        print(start)

    payload = {
        'venueAccountId': account_ids,
        'startTs': start
    }

    try:
        response = requests.get(full_url, headers=headers, params=payload)
        data = response.json()
    except Exception as e:
        print(f"API request failed: {e}")
        return pd.DataFrame()

    entries = data.get('result', {}).get('entries', [])
    if not entries:
        return pd.DataFrame()

    df = pd.DataFrame(entries)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df[['timestamp', 'symbol', 'quantity', 'price', 'aggressor', 'instrumentType', 'venue', 'side', 'type', 'indexPrice', 'underlyingPrice']]
    df[['quantity', 'price']] = df[['quantity', 'price']].astype(float)

    # --- Volume Calculation ---
    btc_denom = {'farbfoxtrot_btc', 'optalphadelta_btc', 'opttangopapa_btc'}  # Set of PMs that need BTC denominated volume

    def get_underlying_from_symbol(symbol):
        # For Deribit, symbol like BTC-25JUL25-115000-C or ETH-25JUL25-3500-C
        return symbol.split('-')[0] if '-' in symbol else symbol

    df['underlying'] = df.apply(
        lambda row: get_underlying_from_symbol(row['symbol']) if row['instrumentType'] == 'OPTIONS' else None,
        axis=1
    )

    # Cache for price lookups to avoid repeated API calls
    price_cache = {}
    def get_price(symbol):
        if symbol not in price_cache:
            price_cache[symbol] = get_latest_price(venue='BINANCE', symbol=symbol)
        return price_cache[symbol]

    def compute_volume(row):
        if row['instrumentType'] == 'OPTIONS':
            # For options, volume is number of contracts
            contracts = abs(row['quantity'])
            if pm in btc_denom:
                if row['underlying'] == 'BTC':
                    return contracts
                elif row['underlying'] == 'ETH':
                    btc_eth_price = get_price('BTCUSDT') / get_price('ETHUSDT')
                    return contracts * btc_eth_price
                else:
                    try:
                        symbol_usdt = f"{row['underlying']}USDT"
                        price = get_price('BTCUSDT') / get_price(symbol_usdt)
                        return contracts * price
                    except Exception:
                        return 0
            else:
                return contracts * row['price']  # Not BTC-denominated, use notional
        else:
            # For non-options
            notional = abs(row['quantity']) * row['price'] if row['symbol'] != 'BTC-PERPETUAL' else abs(row['quantity'])
            if pm in btc_denom:
                return notional / row['price'] if row['price'] else 0
            else:
                return notional

    df['volume'] = df.apply(compute_volume, axis=1)
    df['pm'] = pm
    df['day'] = df['timestamp'].dt.floor('d')
    df['exec_type'] = df['aggressor'].apply(lambda x: 'T' if x else 'M')

    # Group and aggregate
    df = df.groupby(['day', 'pm', 'instrumentType', 'exec_type', 'venue'], as_index=False).agg({'volume': 'sum'})
    df.rename(columns={'day': 'timestamp', 'instrumentType': 'instrument_type'}, inplace=True)
    print(df)
    return df


def get_mapping_df(group='fund'):
    try:
        mapping_df = sheet_utils.get_dataframe(url='https://docs.google.com/spreadsheets/d/1Sh-xocICpDYQ4QP_Xrm-5KAJ3u_aSoCzWQ_0QVPfV4Y/edit?gid=397850281#gid=397850281', sheet_name=group, evaluate=True)
        mapping_df = mapping_df[['haruko id', 'pm']]
        mapping_df = mapping_df.dropna()
        # pm_mapping = mapping_df.set_index('haruko id')['db id'].to_dict()
        print(mapping_df)
        return mapping_df
    except Exception as e:
        print('google sheet get mapping_df error', e)

def fund_trading_volume():
    mapping_df = get_mapping_df(group='fund')
    if mapping_df.empty:
        return
    trading_vol_list = []

    for _, row in mapping_df.iterrows():
        if row['pm'] == 'cpas' or row['pm'] == 'aurorecta':
            continue
        print(row['haruko id'], row['pm'])
        account_ids = int(row['haruko id'])
        pm = row['pm']
        df = get_trading_vol(account_ids=account_ids, pm=pm)
        # db_utils.df_to_table(table_name='trading_volume', df=df)
        trading_vol_list.append(df)

    df = pd.concat(trading_vol_list)
    df.loc[df['pm'].isin(credentials.BTC_DENOMINATED), 'pm'] += '_btc' # adding _btc to it because we want to show USDT-based trading volume for romeo

    print(df)
    db_utils.update_trading_volume_on_conflict(df=df, table_name='trading_volume')

def job():
    try:
        fund_trading_volume()
        # trial_trading_volume()
    except Exception as e:
        print(e)
    # sheet_utils.set_dataframe(df=df, url='https://docs.google.com/spreadsheets/d/12mO3fI8eqWPS7zp3EJ1Ic3pGobsyr6yr3XJvOMBtmkI/edit?gid=833083086#gid=833083086', sheet_name='Sheet9')

# schedule.every().hour.at(":01").do(job)
# print('running scheduled job')

# while True:
#     schedule.run_pending()
#     time.sleep(1)

# job()