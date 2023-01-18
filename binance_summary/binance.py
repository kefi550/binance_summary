import argparse
import datetime
import hmac
import hashlib
import json
import os
import requests
from urllib import parse

BINANCE_API_KEY = os.environ["BINANCE_API_KEY"]
BINANCE_API_SECRET = os.environ["BINANCE_API_SECRET"]
BINANCE_API_URL = "https://api.binance.com"


def _signature(secret: str, data: str):
    s = hmac.new(secret.encode('utf-8'), data.encode('utf-8'),
                 digestmod=hashlib.sha256)
    return s.hexdigest()


def call_binance_user_api(path: str, method: str = 'GET', params: dict = {}) -> dict:
    timestamp = int(datetime.datetime.now(
        datetime.timezone.utc).timestamp() * 1000)

    if not path.startswith('/'):
        path = '/' + path
    url = BINANCE_API_URL + path
    params['timestamp'] = timestamp
    query = parse.urlencode(params)
    signature = _signature(BINANCE_API_SECRET, query)
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': BINANCE_API_KEY}
    r = requests.request(method=method,
                         url=url,
                         params=params,
                         headers=headers,
                         )
    return r.json()


def call_binance_public_api(path: str, method: str = 'GET', params: dict = {}) -> dict:
    if not path.startswith('/'):
        path = '/' + path
    url = BINANCE_API_URL + path
    headers = {'X-MBX-APIKEY': BINANCE_API_KEY}
    r = requests.request(method=method,
                         url=url,
                         params=params,
                         headers=headers,
                         )
    return r.json()


def get_latest_balances() -> list[dict]:
    snapshot_vos = get_balances()
    latest_snapshot = sorted(snapshot_vos, key=lambda x: x['updateTime'])[-1]
    # 重複して入ってくる場合があるので重複排除
    return list(map(json.loads, set(map(json.dumps, latest_snapshot['data']['balances']))))


def get_balances(days=29) -> list[dict]:
    path = '/sapi/v1/accountSnapshot'
    latest_timestamp = int(datetime.datetime.today().astimezone(
        datetime.timezone.utc).timestamp() * 1000)
    start_timestamp = int((datetime.datetime.today(
    ) - datetime.timedelta(days=days)).astimezone(datetime.timezone.utc).timestamp() * 1000)
    params = {
        "type": "SPOT",
        "startTime": start_timestamp,
        "endTime": latest_timestamp,
    }
    snapshot_vos = call_binance_user_api(path, params=params)['snapshotVos']
    for v in snapshot_vos:
        v['updateDatetime'] = str(
            datetime.date.fromtimestamp(float(v['updateTime']) / 1000))
    return snapshot_vos


def get_binance_ticker(symbol: str, target_symbol: str = "USDT") -> float:
    path = '/api/v3/ticker'
    symbol = normalize_symbol(symbol)
    params = {
        "symbol": symbol + target_symbol,
    }
    ticker = call_binance_public_api(path, params=params)
    if 'lastPrice' in ticker.keys():
        return float(ticker['lastPrice'])
    # 検索引っかからなかったら無視として0を返す
    return 0.0


def get_usd_jpy_balance() -> float:
    url = 'https://api-pub.bitfinex.com/v2/ticker/tUSDJPY'
    r = requests.request(method='GET',
                         url=url,
                         )
    usd_jpy_balance = r.json()[0]
    return usd_jpy_balance


def normalize_symbol(symbol: str) -> str:
    if symbol.startswith('LD'):
        symbol = symbol[2:]
    return symbol


def get_latest_assets_jpy(asset: str = None):
    jpy_assets = {}
    latest_binance_balances = get_latest_balances()
    usd_jpy_balance = get_usd_jpy_balance()
    print(latest_binance_balances)
    for b in latest_binance_balances:
        symbol = normalize_symbol(b['asset'])
        symbol_free = float(b['free'])
        usd_balance = get_binance_ticker(symbol)
        jpy = usd_balance * symbol_free * usd_jpy_balance
        jpy_assets[symbol] = jpy_assets.get(symbol, 0) + jpy
    if asset in jpy_assets.keys():
        return jpy_assets[asset]
    return jpy_assets


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("asset", nargs="?", help='コイン名')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    print(get_latest_assets_jpy(args.asset))
