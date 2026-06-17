import db_utils
import sheet_utils
import pandas as pd
import credentials
import numpy as np
import get_latest_price


query = '''SELECT
  m.pm_group,
  te.timestamp,
  te.symbol,
  te.size,
  m.if_btc
FROM transfer_events te
JOIN pm_mapping m
  ON m.pm = te.pm
 AND m.active = true
 AND m.if_btc = true
JOIN inflight_state s
  ON s.pm = m.pm_group
WHERE te."timestamp" > s.last_zero_ts and te."timestamp" < '2026-01-20 22:40:00';'''

# query = '''SELECT *
# FROM transfer_events;'''

df = db_utils.get_db_table(query=query)

# transfer_df = db_utils.get_db_table(query=query)

# df = pd.merge(transfer_df, grouping_df)

URL = 'https://docs.google.com/spreadsheets/d/1U6hyusEfooX7-PNxMMClXjiUAaxswQjGtW9xYOlbr1w/edit?gid=1211338992#gid=1211338992'
SHEET_NAME = 'inflight_record'

STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}

def add_amount_column(df):
    # 1) 做一個簡單的 price cache，避免每 row 打一次 API
    price_cache = {}

    def px(pair: str) -> float:
        if pair not in price_cache:
            p = get_latest_price.latest_price(pair)
            if p is None or p <= 0:
                raise ValueError(f"latest_price failed for {pair}: {p}")
            price_cache[pair] = p
        return price_cache[pair]

    btcusdt = px("BTCUSDT")

    # 2) 把每個 symbol 的「1 顆」換算成 USDT 價格
    def coin_to_usdt_price(coin: str) -> float:
        coin = coin.upper()

        # stablecoin 視為 1 USDT（如果你想更精準，可改成抓 USDCUSDT）
        if coin in STABLES:
            return 1.0

        if coin == "BTC":
            return btcusdt

        # 最常見：COINUSDT
        pair = f"{coin}USDT"
        p = get_latest_price.latest_price(pair)
        if p and p > 0:
            price_cache[pair] = p
            return p

        # fallback：COINUSDC（再乘 USDCUSDT 轉回 USDT）
        pair2 = f"{coin}USDC"
        p2 = get_latest_price.latest_price(pair2)
        if p2 and p2 > 0:
            price_cache[pair2] = p2
            usdcusdt = px("USDCUSDT")  # 若你覺得 USDC=1 也可以直接用 1.0
            return p2 * usdcusdt

        raise ValueError(f"Cannot find a USDT price for coin={coin}")

    # 3) 先算 notional_usdt，再依 if_btc 決定 amount 單位
    #    假設 df['size'] 是「幣數」，例如 symbol=ETH size=0.5 -> 0.5 ETH
    df = df.copy()
    df["coin_usdt_px"] = df["symbol"].apply(coin_to_usdt_price)
    df["notional_usdt"] = df["size"] * df["coin_usdt_px"]

    df["normalized_amount"] = np.where(
        df["if_btc"].astype(bool),
        df["notional_usdt"] / btcusdt,  # -> BTC 顆數
        df["notional_usdt"],            # -> USDT
    )

    # 如果你不想留下中間欄位，可以最後 drop
    # df.drop(columns=["coin_usdt_px", "notional_usdt"], inplace=True)

    return df

enriched_df = add_amount_column(df)
print('enriched_df')
print(enriched_df)

pm_group_inflight = (
    enriched_df
    .groupby("pm_group", as_index=False)["normalized_amount"]
    .sum()
)

pm_group_inflight["inflight_amount"] = np.where(
        pm_group_inflight["normalized_amount"] > -0.00009,
        0,
        pm_group_inflight["normalized_amount"],
    )


required_pm_groups = [
    "sp2-sma-victorcharliebtc",
    "sp2-sma-romeocharliebtc",
]

pm_group_inflight = (
    pm_group_inflight
    .set_index("pm_group")
    .reindex(required_pm_groups, fill_value=0)
    .reset_index()
)
print('pm_group_inflight')
print(pm_group_inflight)

latest_ts = (
    enriched_df.groupby("pm_group", as_index=False)["timestamp"]
      .max()
      .rename(columns={"pm_group": "pm", "timestamp": "max_ts"})
)
print('latest_ts')
print(latest_ts)

pm_group_inflight.rename(columns={'pm_group':'pm'}, inplace=True)
data_to_write = pm_group_inflight[['pm', 'inflight_amount']]

sheet_utils.set_dataframe(data_to_write, URL, SHEET_NAME)

data_to_write = data_to_write.merge(latest_ts, on="pm", how="left")
db_utils.upsert_inflight_state(data_to_write)