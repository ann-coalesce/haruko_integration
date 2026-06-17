import requests
import json
class HarukoAPI:
    def __init__(self, api_token='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiYW5uQGNvYWxlc2NlLnBhcnRuZXJzIiwiY29tcGFueSI6ImNvYWxlc2NlIHBhcnRuZXJzIiwiZG9tYWluIjoiY29hbGVzY2UucGFydG5lcnMiLCJnbG9iYWxUcmFpdHMiOlsiQ09NUEFOWV9BRE1JTiIsIlVTRVJfQURNSU4iXSwiaW5zdGFuY2VzIjpbeyJpbnN0YW5jZU5hbWUiOiJjb2FsZXNjZSBwYXJ0bmVycyIsInRyYWl0cyI6W119XSwiaWF0IjoxNzI3NzQ2NzE4fQ.rbT9Saz4XyZG0629KH3dgJs_rGffoSRNKJV1tG9b5BY', base_url='https://co1.haruko.io'):
        """
        Initialize the API client with the base URL and API token.

        :param api_token: Your Haruko API authentication token.
        :param base_url: The base URL of your Haruko instance.
        """
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer <{self.api_token}>',
            'Content-Type': 'application/json'
        }

    def _get_full_url(self, endpoint):
        """
        Constructs the full URL for the API request.

        :param endpoint: API endpoint path, e.g., '/cefi/api/admin/group'
        :return: Full URL for the request.
        """
        return f"{self.base_url}{endpoint}"

    def _handle_response(self, response):
        """
        Handles the API response, checking for success or failure.

        :param response: Response object from the requests library.
        :return: Parsed response data or an error message.
        """
        if response.status_code in [200, 201]:
            try:
                return response.json()
            except ValueError:
                return {"message": "Success", "status_code": response.status_code}
        else:
            return {"error": response.text, "status_code": response.status_code}

    def get_group(self):
        url = self._get_full_url(f"/cefi/api/admin/group")
        response = requests.get(url, headers=self.headers)
        return self._handle_response(response)

    def get_account_summary(self, accountIds):
        payload = {'venueAccountIds':accountIds}
        url = self._get_full_url(f"/cefi/api/summary/accounts")
        print('base url',url)
        response = requests.get(url, headers=self.headers, params=payload)
        # print(response.content)
        return self._handle_response(response)
    
    def get_aggregate_transfers(self, accountIds, startTs=None):
        if startTs:
            payload = {'venueAccountIds':accountIds, 'startTs':startTs}
        else:
            payload = {'venueAccountIds':accountIds}
        
        url = self._get_full_url(f"/cefi/api/aggregate/transfers")
        # print('base url',url)
        response = requests.get(url, headers=self.headers, params=payload)
        # print(response.content)
        return self._handle_response(response)

    def get_latest_price(self, venue='BINANCE'):
        url = self._get_full_url(f"/cefi/api/pricing/instruments/live")
        print('base url',url)
        payload = {'venue':venue}
        response = requests.get(url, headers=self.headers, params=payload)
        print(response.content)
        return self._handle_response(response)
    
    def get_aggregate_balance(self, accountIds):
        payload = {'venueAccountIds':accountIds}
        url = self._get_full_url(f"/cefi/api/aggregate/balance")
        print('base url',url)
        response = requests.get(url, headers=self.headers, params=payload)
        print(response.content)
        return self._handle_response(response)


    def get_balance(self, accountId):
        payload = {'venueAccountId':accountId}
        url = self._get_full_url(f"/cefi/api/balance")
        print('base url',url)
        response = requests.get(url, headers=self.headers, params=payload)
        # print(response.content)
        return self._handle_response(response)