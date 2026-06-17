import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd


def set_dataframe(df, url, sheet_name, row=1, col=1, include_column_header=True):
    try:
        gc = gspread.service_account(filename="pms-sheets-1669aad2a089.json")
        sh = gc.open_by_url(url=url)
        print(sh)

        worksheet = sh.worksheet(sheet_name)
        print(worksheet)
        set_with_dataframe(dataframe=df, worksheet=worksheet, row=row, col=col, include_column_header=include_column_header)
    except Exception as e:
        print(e)
def get_dataframe(url, sheet_name, evaluate=True):
    try:
        gc = gspread.service_account(filename="pms-sheets-1669aad2a089.json")
        sh = gc.open_by_url(url=url)

        worksheet = sh.worksheet(sheet_name)
        df = get_as_dataframe(worksheet, evaluate_formulas=evaluate)
        return df
    except Exception as e:
        print('google sheet get dataframe error', e)
        return pd.DataFrame()

def get_last_row(url, sheet_name):
    gc = gspread.service_account(filename="pms-sheets-1669aad2a089.json")
    sh = gc.open_by_url(url=url)

    worksheet = sh.worksheet(sheet_name)
    row = len(worksheet.col_values(1))

    return row


def clear_range(url, sheet_name, range):
    # try:
        gc = gspread.service_account(filename="pms-sheets-1669aad2a089.json")
        sh = gc.open_by_url(url=url)

        worksheet = sh.worksheet(sheet_name)
        worksheet.batch_clear([range])

    # except Exception as e:
        # print("error", e)
        return