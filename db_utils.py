import time
import pandas as pd
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine
import db_constants
from psycopg2.extras import execute_values
from datetime import timedelta

connection_string = f'postgresql+psycopg2://{db_constants.DB_USER}:{db_constants.DB_PASSWORD}@{db_constants.DB_HOST}:{db_constants.DB_PORT}/{db_constants.DB_NAME}'
# engine = create_engine(connection_string)

def execute_query(query):
    conn = psycopg2.connect(dbname=db_constants.DB_NAME, user=db_constants.DB_USER, password=db_constants.DB_PASSWORD, host=db_constants.DB_HOST, port='5432', sslmode='require')
    cursor = conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
    print(cursor)
    print(query)

    try:
        # Execute the SQL query
        cursor.execute(query)
        conn.commit()
        cursor.close()
        conn.close()
    except psycopg2.DatabaseError as e:
        # Rollback the transaction in case of an error
        # alert.send_notif(message='【DB Error】\nIn Fund Balance Data >> update_db >> execute_query\n'+str(e), chat_id='-4236738717') # api error group
        conn.rollback()
        print(f"An error occurred: {e}")


def update_balance_data(df, source):
    engine = create_engine(connection_string)
    delete_query = f'DELETE FROM fund_balance_data WHERE source in ({source});'
    execute_query(delete_query)

    try:
        df.to_sql('fund_balance_data', engine, if_exists='append', index=False)
        print(f"Updated balances for {source}")
    except Exception as e:
        # alert.send_notif(message='【DB Error】\nIn Fund Balance Data >> update_db >> update_balance_data\n'+str(e), chat_id='-4236738717') # api error group
        print(f'Error encountered when updating fund_balance_data for {source}', e)
    
    engine.dispose()

def get_db_table(query):
    engine = create_engine(connection_string)
    try:
        df = pd.read_sql(query, engine)
        engine.dispose()
        return df
    except Exception as e:
        # alert.send_notif(message='【DB Error】\nIn Fund Balance Data >> update_db >> get_db_table\n'+str(e), chat_id='-4236738717') # api error group
        print(f'Error encountered getting sql table with this query {query}: ', e)
        engine.dispose()
        return pd.DataFrame()
    

def df_to_table(table_name, df):
    engine = create_engine(connection_string)
    try:
        df.to_sql(table_name, engine, if_exists='append', index=False)
    except Exception as e:
        # alert.send_notif(message='【DB Error】\nIn Fund Balance Data >> update_db >> df_to_table\n'+str(e), chat_id='-4236738717') # api error group
        print(f'Error encountered when updating {table_name}', e)
    
    engine.dispose()

def df_replace_table(table_name, df):
    engine = create_engine(connection_string)
    try:
        df.to_sql(table_name, engine, if_exists='replace', index=False)
    except Exception as e:
        # alert.send_notif(message='【DB Error】\nIn Fund Balance Data >> update_db >> df_to_table\n'+str(e), chat_id='-4236738717') # api error group
        print(f'Error encountered when updating {table_name}', e)
    
    engine.dispose()


def update_trading_volume_on_conflict(table_name,df):
    conn = psycopg2.connect(dbname=db_constants.DB_NAME, user=db_constants.DB_USER, password=db_constants.DB_PASSWORD, host=db_constants.DB_HOST, port='5432', sslmode='require')
    try:
        # Insert/Update query with ON CONFLICT
        query = f"""
        INSERT INTO {table_name} (timestamp, pm, instrument_type, exec_type, venue, volume)
        VALUES %s
        ON CONFLICT (timestamp, pm, instrument_type, exec_type, venue)
        DO UPDATE SET 
            volume = EXCLUDED.volume,
            instrument_type = EXCLUDED.instrument_type;
        """

        # Convert DataFrame to list of tuples
        data_to_insert = list(df.itertuples(index=False, name=None))

        with conn:
            with conn.cursor() as cur:
                # Use execute_values for bulk insert/update
                execute_values(cur, query, data_to_insert)

        conn.close()
    
    except Exception as e:
        conn.rollback()
        print(f'DB update trading volume error {e}')


def insert_transfer_events_on_conflict(df):
    """
    Inserts transfer events into the database table using ON CONFLICT DO NOTHING
    to skip duplicates based on (timestamp, pm, symbol) unique constraint.
    """
    conn = psycopg2.connect(dbname=db_constants.DB_NAME, user=db_constants.DB_USER, password=db_constants.DB_PASSWORD, host=db_constants.DB_HOST, port='5432', sslmode='require')
    try:
        # Insert query that skips duplicates
        query = f"""
        INSERT INTO transfer_events (timestamp, symbol, size, haruko_id, pm)
        VALUES %s
        ON CONFLICT (timestamp, pm, symbol) DO NOTHING;
        """

        # Convert DataFrame to list of tuples
        data_to_insert = list(df.itertuples(index=False, name=None))

        with conn:
            with conn.cursor() as cur:
                execute_values(cur, query, data_to_insert)
                print(f"{len(data_to_insert)} rows processed for transfer_events (duplicates skipped).")

    except Exception as e:
        conn.rollback()
        print(f"DB insert error for transfer_events: {e}")

    finally:
        conn.close()



def upsert_inflight_state(df):
    """
    Expects df columns: ['pm', 'inflight_amount', 'max_ts']
    """
    required_cols = {"pm", "inflight_amount", "max_ts"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"upsert_inflight_state expects columns {required_cols}, got {set(df.columns)}")

    df2 = df.copy()
    df2["pm"] = df2["pm"].astype(str)
    df2["inflight_amount"] = df2["inflight_amount"].astype(float)
    print('df2')
    print(df2)
    # max_ts: NaT -> None
    df2["max_ts"] = df2["max_ts"].where(pd.notnull(df2["max_ts"]), None)
    print('df2')
    print(df2)
    def calc_candidate(row):
        # inflight != 0: 絕對不更新 last_zero_ts
        if row["inflight_amount"] != 0:
            return None

        ts = row["max_ts"]
        if ts is None:
            return None

        # pandas Timestamp -> python datetime
        if isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        return ts + timedelta(minutes=1)

    df2["last_zero_ts_candidate"] = df2.apply(calc_candidate, axis=1)

    # ✅ 最後再清一次：NaT/NaN -> None，避免 'NaT' 進 DB
    df2 = df2.replace({pd.NaT: None})
    print('df2')
    print(df2)

    data_to_insert = list(
        df2[["pm", "inflight_amount", "last_zero_ts_candidate"]]
        .itertuples(index=False, name=None)
    )

    print("data_to_insert")
    print(data_to_insert)

    conn = psycopg2.connect(
        dbname=db_constants.DB_NAME,
        user=db_constants.DB_USER,
        password=db_constants.DB_PASSWORD,
        host=db_constants.DB_HOST,
        port='5432',
        sslmode='require'
    )

    try:
        query = """
        INSERT INTO inflight_state (pm, inflight_amount, last_zero_ts, updated_at)
        VALUES %s
        ON CONFLICT (pm) DO UPDATE
        SET
          inflight_amount = EXCLUDED.inflight_amount,
          updated_at = NOW(),
          last_zero_ts = CASE
              WHEN EXCLUDED.inflight_amount = 0
                   AND EXCLUDED.last_zero_ts IS NOT NULL
                THEN EXCLUDED.last_zero_ts
              ELSE inflight_state.last_zero_ts
          END;
        """

        template = "(%s, %s, %s, NOW())"

        with conn:
            with conn.cursor() as cur:
                execute_values(cur, query, data_to_insert, template=template)

        print(f"{len(data_to_insert)} rows upserted into inflight_state.")

    except Exception as e:
        conn.rollback()
        print(f"DB upsert error for inflight_state: {e}")

    finally:
        conn.close()