"""
Trading volume calculation and tracking for cryptocurrency accounts.
Retrieves trade data from Haruko API and stores aggregated volumes.
"""

import argparse
import credentials
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List
import pandas as pd
import sheet_utils
import db_utils


class HarukoAPIClient:
    """Client for interacting with Haruko API endpoints."""

    BASE_URL = 'https://co1.haruko.io'

    def __init__(self):
        self.headers = {
            'Authorization': f'Bearer <{credentials.HARUKO_KEY}>',
            'Content-Type': 'application/json'
        }
        self._price_cache: Dict[str, float] = {}

    def get_latest_price(self, venue: str = 'BINANCE', symbol: str = 'BTCUSDT') -> Optional[float]:
        """
        Fetch the latest price for a given symbol from a venue.

        Args:
            venue: Trading venue name
            symbol: Trading symbol

        Returns:
            Current price or None if not found
        """
        # Check cache first
        cache_key = f"{venue}:{symbol}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        endpoint = '/cefi/api/pricing/instruments/live'
        full_url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.get(
                full_url,
                headers=self.headers,
                params={'venue': venue}
            )
            response.raise_for_status()
            data = response.json()

            for instrument in data.get("result", {}).get("instruments", []):
                if instrument["symbol"] == symbol:
                    price = instrument["referencePrice"]
                    self._price_cache[cache_key] = price
                    print(f'Price for {symbol}: {price}')
                    return price

        except requests.exceptions.RequestException as e:
            print(f"Error fetching price for {symbol}: {e}")

        return None

    def get_trades(
        self,
        account_ids: int,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch trade data for specified account IDs.

        Args:
            account_ids: Account ID to fetch trades for
            start_ts: Start timestamp in milliseconds (defaults to today 00:00 UTC)
            end_ts: End timestamp in milliseconds

        Returns:
            DataFrame containing trade data
        """
        endpoint = '/cefi/api/trades'
        full_url = f"{self.BASE_URL}{endpoint}"

        # Default to start of current day if not provided
        if start_ts is None:
            start_of_day = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            start_ts = int(start_of_day.timestamp() * 1000)

        payload = {
            'venueAccountId': account_ids,
            'startTs': start_ts
        }

        if end_ts:
            payload['endTs'] = end_ts

        try:
            response = requests.get(full_url, headers=self.headers, params=payload)
            response.raise_for_status()
            data = response.json()

            entries = data.get('result', {}).get('entries', [])
            if not entries:
                return pd.DataFrame()

            df = pd.DataFrame(entries)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)

            # Select and reorder columns
            columns = [
                'timestamp', 'symbol', 'quantity', 'price', 'aggressor',
                'instrumentType', 'venue', 'side', 'type', 'indexPrice',
                'underlyingPrice'
            ]
            df = df[columns]
            df[['quantity', 'price']] = df[['quantity', 'price']].astype(float)

            return df

        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return pd.DataFrame()


class VolumeCalculator:
    """Calculates trading volumes with proper denomination handling."""

    BTC_DENOMINATED_PMS = {'farbfoxtrot', 'optalphadelta', 'opttangopapa'}

    def __init__(self, api_client: HarukoAPIClient):
        self.api_client = api_client

    @staticmethod
    def extract_underlying(symbol: str) -> str:
        """Extract underlying asset from option symbol (e.g., BTC-25JUL25-115000-C -> BTC)."""
        return symbol.split('-')[0] if '-' in symbol else symbol

    def calculate_volume(self, row: pd.Series, pm: str) -> float:
        """
        Calculate volume for a trade based on instrument type and PM requirements.

        Args:
            row: Trade data row
            pm: Portfolio manager identifier

        Returns:
            Calculated volume
        """
        is_btc_denominated = pm in self.BTC_DENOMINATED_PMS

        if row['instrumentType'] == 'OPTIONS':
            return self._calculate_options_volume(row, pm, is_btc_denominated)
        else:
            return self._calculate_spot_volume(row, is_btc_denominated)

    def _calculate_options_volume(
        self,
        row: pd.Series,
        pm: str,
        is_btc_denominated: bool
    ) -> float:
        """Calculate volume for options trades."""
        contracts = abs(row['quantity'])

        if not is_btc_denominated:
            return contracts * row['price']  # Notional value

        underlying = self.extract_underlying(row['symbol'])

        if underlying == 'BTC':
            return contracts
        elif underlying == 'ETH':
            btc_price = self.api_client.get_latest_price('BINANCE', 'BTCUSDT')
            eth_price = self.api_client.get_latest_price('BINANCE', 'ETHUSDT')
            if btc_price and eth_price:
                return contracts * (btc_price / eth_price)
        else:
            try:
                symbol_usdt = f"{underlying}USDT"
                btc_price = self.api_client.get_latest_price('BINANCE', 'BTCUSDT')
                asset_price = self.api_client.get_latest_price('BINANCE', symbol_usdt)
                if btc_price and asset_price:
                    return contracts * (btc_price / asset_price)
            except Exception as e:
                print(f"Error calculating volume for {underlying}: {e}")

        return 0

    def _calculate_spot_volume(self, row: pd.Series, is_btc_denominated: bool) -> float:
        """Calculate volume for spot/perpetual trades."""
        if row['symbol'] == 'BTC-PERPETUAL':
            notional = abs(row['quantity'])
        else:
            notional = abs(row['quantity']) * row['price']

        if is_btc_denominated and row['price']:
            return notional / row['price']

        return notional


class TradingVolumeProcessor:
    """Process and aggregate trading volume data."""

    def __init__(self, api_client: HarukoAPIClient):
        self.api_client = api_client
        self.volume_calculator = VolumeCalculator(api_client)

    def process_account_trades(
        self,
        account_id: int,
        pm: str,
        start_ts: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Process trades for a single account and calculate volumes.

        Args:
            account_id: Account identifier
            pm: Portfolio manager identifier
            start_ts: Start timestamp in milliseconds

        Returns:
            Aggregated volume DataFrame
        """
        df = self.api_client.get_trades(account_id, start_ts)

        if df.empty:
            return pd.DataFrame()

        # Calculate volume for each trade
        df['volume'] = df.apply(
            lambda row: self.volume_calculator.calculate_volume(row, pm),
            axis=1
        )

        # Add metadata
        df['pm'] = pm
        df['day'] = df['timestamp'].dt.floor('d')
        df['exec_type'] = df['aggressor'].apply(lambda x: 'T' if x else 'M')

        # Aggregate by day, pm, instrument type, execution type, and venue
        aggregated = df.groupby(
            ['day', 'pm', 'instrumentType', 'exec_type', 'venue'],
            as_index=False
        ).agg({'volume': 'sum'})

        aggregated.rename(
            columns={'day': 'timestamp', 'instrumentType': 'instrument_type'},
            inplace=True
        )

        print(f"Processed {len(df)} trades for {pm}")
        print(aggregated)

        return aggregated

    def process_fund_accounts(self, start_ts: Optional[int] = None) -> pd.DataFrame:
        """
        Process all fund accounts from mapping sheet.

        Args:
            start_ts: Start timestamp in milliseconds (defaults to today 00:00 UTC)

        Returns:
            Combined DataFrame with all fund trading volumes
        """
        mapping_df = self._get_account_mapping('fund')

        if mapping_df.empty:
            print("No account mappings found")
            return pd.DataFrame()

        volume_dfs: List[pd.DataFrame] = []

        for _, row in mapping_df.iterrows():
            pm = row['pm']

            # Skip specific PMs
            if pm in {'cpas', 'aurorecta'}:
                continue

            account_id = int(row['haruko id'])
            print(f"Processing account {account_id} for {pm}")

            df = self.process_account_trades(account_id, pm, start_ts=start_ts)
            if not df.empty:
                volume_dfs.append(df)

        if not volume_dfs:
            return pd.DataFrame()

        combined_df = pd.concat(volume_dfs, ignore_index=True)

        # Add _btc suffix for BTC-denominated PMs
        btc_mask = combined_df['pm'].isin(credentials.BTC_DENOMINATED)
        combined_df.loc[btc_mask, 'pm'] += '_btc'

        return combined_df

    @staticmethod
    def _get_account_mapping(group: str = 'fund') -> pd.DataFrame:
        """
        Retrieve account mapping from Google Sheets.

        Args:
            group: Sheet name to retrieve (e.g., 'fund', 'trial')

        Returns:
            DataFrame with account mappings
        """
        sheet_url = 'https://docs.google.com/spreadsheets/d/1Sh-xocICpDYQ4QP_Xrm-5KAJ3u_aSoCzWQ_0QVPfV4Y/edit?gid=397850281#gid=397850281'

        try:
            mapping_df = sheet_utils.get_dataframe(
                url=sheet_url,
                sheet_name=group,
                evaluate=True
            )
            mapping_df = mapping_df[['haruko id', 'pm']].dropna()
            print(f"Retrieved {len(mapping_df)} account mappings")
            return mapping_df

        except Exception as e:
            print(f'Error retrieving account mappings: {e}')
            return pd.DataFrame()


def parse_start_date(date_str: str) -> int:
    """
    Convert a YYYY-MM-DD date string to a millisecond UTC timestamp at 00:00.

    Args:
        date_str: Date in 'YYYY-MM-DD' format

    Returns:
        Start timestamp in milliseconds
    """
    dt = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def run_trading_volume_job(start_ts: Optional[int] = None):
    """
    Main job function to process and store trading volumes.

    Args:
        start_ts: Start timestamp in milliseconds. If None, defaults to today
                  00:00 UTC (handled downstream in get_trades).
    """
    try:
        api_client = HarukoAPIClient()
        processor = TradingVolumeProcessor(api_client)

        # Process fund accounts
        volume_df = processor.process_fund_accounts(start_ts=start_ts)

        if not volume_df.empty:
            print(f"Storing {len(volume_df)} volume records to database")
            db_utils.update_trading_volume_on_conflict(
                df=volume_df,
                table_name='trading_volume'
            )
        else:
            print("No trading volume data to store")

    except Exception as e:
        print(f"Job failed with error: {e}")

    finally:
        finished_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        print(f"Job finished at: {finished_at}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process and store trading volumes from Haruko API."
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD (UTC 00:00). Defaults to today 00:00 UTC."
    )
    args = parser.parse_args()

    start_ts = parse_start_date(args.start_date) if args.start_date else None
    run_trading_volume_job(start_ts=start_ts)