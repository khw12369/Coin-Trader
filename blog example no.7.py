import requests
import time
import hashlib
import hmac

# 바이낸스 API 엔드포인트
BASE_URL = "https://fapi.binance.com"

# 바이낸스 API 키 (API 호출을 위해 필요)
API_KEY = 'HgoM8YxJ5DZwJXaVRZ87JEEeGpmWDSAXGSzxGeCsM25tqbi6xPHDTT2fMXQFt9bR'
API_SECRET = '8t03t3Fa1GQZCD2f99r3HEE9GYVeXNhS4FyjZpCVPTbGofmoPYATilUCoXWJKixf'

# 헤더 설정
headers = {
    'X-MBX-APIKEY': API_KEY
}

# 서버 시간을 가져오는 함수
def get_server_time():
    url = f"{BASE_URL}/fapi/v1/time"
    response = requests.get(url)
    return response.json()['serverTime']

# 요청에 서명을 추가하는 함수
def get_max_leverage(symbol):
    url = f"{BASE_URL}/fapi/v1/leverageBracket"
    timestamp = int(time.time() * 1000)
    params = {
        "symbol": symbol,
        "timestamp": timestamp
    }
    query_string = '&'.join([f"{key}={params[key]}" for key in params])
    signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    print(data)
    # 각 종목에 대해 최대 레버리지를 찾음
    for bracket in data:
        if bracket['symbol'] == symbol:
            return max([int(br['initialLeverage']) for br in bracket['brackets']])
    return None

# 사용자가 입력한 레버리지와 비교하여 최소값을 설정
def set_leverage(symbol, user_leverage):
    max_leverage = get_max_leverage(symbol)

    if max_leverage is None:
        print(f"{symbol}의 최대 레버리지를 가져올 수 없습니다.")
        return

    leverage_to_set = min(max_leverage, user_leverage)
    # 바이낸스 서버 시간 가져오기
    timestamp = get_server_time()
    params = {
        "symbol": symbol,
        "leverage": leverage_to_set,
        "timestamp": timestamp
    }

    #signed_payload = sign_request(payload)
    query_string = '&'.join([f"{key}={params[key]}" for key in params])
    signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature
    set_leverage_url = f"{BASE_URL}/fapi/v1/leverage"
    response = requests.post(set_leverage_url, headers=headers, params=params)

    if response.status_code == 200:
        print(f"{symbol}에 대해 레버리지 {leverage_to_set}로 설정되었습니다.")
    else:
        print(f"레버리지 설정 실패: {response.json()}")

# 사용 예시
symbol = "BTCUSDT"  # 레버리지를 설정하고 싶은 종목
user_leverage = 200  # 사용자가 원하는 레버리지 값

set_leverage(symbol, user_leverage)
