import requests
import pandas as pd
import time

# Binance Futures API URL
BASE_URL = "https://fapi.binance.com"


def get_ohlcv_data(symbol, interval='1m', limit=500):
    """
    바이낸스 선물 시장에서 심볼의 OHLCV 데이터를 가져옵니다.
    :param symbol: 거래할 심볼 (예: 'BTCUSDT')
    :param interval: 데이터 간격 (예: '1m', '5m', '15m', '1h', '1d')
    :param limit: 가져올 데이터의 개수 (최대 1500)
    :return: OHLCV 데이터 (DataFrame)
    """
    endpoint = "/fapi/v1/klines"
    url = BASE_URL + endpoint

    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }

    response = requests.get(url, params=params)

    # 요청에 실패한 경우 예외를 발생시킵니다.
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.text}")

    # JSON 형식의 응답 데이터를 파이썬 리스트로 변환
    data = response.json()

    # OHLCV 데이터를 DataFrame으로 변환
    ohlcv = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])

    # 필요하지 않은 열 제거
    ohlcv = ohlcv[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    ohlcv['timestamp'] = pd.to_datetime(ohlcv['timestamp'], unit='ms')

    return ohlcv


# 예시: BTCUSDT 심볼에 대해 1분 간격의 데이터를 500개 가져오기
if __name__ == "__main__":
    symbol = 'BTCUSDT'
    interval = '1m'  # 간격 설정 (1m, 5m, 15m, 1h, 1d 등)
    limit = 500  # 가져올 캔들 수 (최대 500)

    ohlcv_data = get_ohlcv_data(symbol, interval, limit)
    print(ohlcv_data)
