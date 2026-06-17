import credentials
import requests
import gspread
import time
from datetime import datetime, timezone

def job():
    curr = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    print(curr)
    base_url='https://co1.haruko.io'
    headers = {'Authorization': f'Bearer <{credentials.HARUKO_KEY}>',
                'Content-Type': 'application/json'}
    endpoint = '/cefi/api/balance_update'
    full_url = f"{base_url}{endpoint}"

    print('url',full_url)

    sp1_notional = 0
    sp3_notional = 0

    try:
        gc = gspread.service_account(filename="pms-sheets-1669aad2a089.json")
        print('Q2 Forward')
        sh = gc.open_by_url(url='https://docs.google.com/spreadsheets/d/1URIR-BzlXo9hzCSvg-Ag5r2Ykuf3DpIhPP6xB_bZf88/edit?gid=460726398#gid=460726398')
        worksheet = sh.worksheet('Hermeneutic_Details')
        sp1_notional = float(worksheet.acell('C7').value.replace(',', ''))
        sp3_notional = float(worksheet.acell('D7').value.replace(',', ''))
        print('sp1_notional', sp1_notional)
        print('sp3_notional', sp3_notional)

    except Exception as e:
        print("google sheet alert", e)
    
    if sp1_notional == 0 or sp3_notional == 0:
        return
    
    try:
        payload = {
            "venueAccountId": 37,
            "balances": {
                "USDC": sp1_notional
            }
        }
        print(payload)
        response = requests.post(full_url, headers=headers, json=payload, timeout=10)
        print(response)
        print('Success?', response.ok)
    except Exception as e:
        print('Requests error', e)

    # try:
    #     payload = {
    #         "venueAccountId": 138,
    #         "balances": {
    #             "USDC": sp3_notional
    #         }
    #     }
    #     response = requests.post(full_url, headers=headers, json=payload)
    #     print('Success?', response.ok)
    # except Exception as e:
    #     print('Requests error', e)

job()