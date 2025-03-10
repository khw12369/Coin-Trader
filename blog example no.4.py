import time
import hmac
import hashlib
import requests
import pprint
import config    #api,secret 저장코드

def get_usdm_positions(api_key, api_secret):
    """Retrieve the current positions in the USDM Futures account."""
    endpoint = '/fapi/v2/positionRisk'
    url = 'https://fapi.binance.com' + endpoint

    timestamp = int(time.time() * 1000)
    params = {
        'timestamp': timestamp
    }

    query_string = '&'.join([f"{key}={params[key]}" for key in params])
    signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature

    headers = {
        'X-MBX-APIKEY': api_key
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()

def get_usdm_balance(api_key, api_secret):
    # 엔드포인트 설정
    endpoint = '/fapi/v2/balance'
    url = 'https://fapi.binance.com' + endpoint

    # 타임스탬프 생성
    timestamp = int(time.time() * 1000)

    # 요청 파라미터
    params = {
        'timestamp': timestamp
    }

    # 쿼리 문자열 생성
    query_string = '&'.join([f"{key}={params[key]}" for key in params])

    # 서명 생성
    signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    # 서명 추가
    params['signature'] = signature

    # 헤더 설정
    headers = {
        'X-MBX-APIKEY': api_key
    }

    # GET 요청으로 잔고 호출
    response = requests.get(url, headers=headers, params=params)

    # 응답 결과 반환
    return response.json()

API_KEY = config.API_KEY
API_SECRET = config.API_SECRET

# 잔고 조회
#balance_info = get_usdm_balance(API_KEY, API_SECRET)
#print("Balance Information:")
#print(balance_info[4])

# 포지션 조회
positions_info = get_usdm_positions(API_KEY, API_SECRET)
print("\nPositions Information:")
print(positions_info)