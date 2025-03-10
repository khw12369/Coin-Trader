import requests
import time
import hmac
import hashlib

# 바이낸스 API 키와 시크릿 키
API_KEY = 'HgoM8YxJ5DZwJXaVRZ87JEEeGpmWDSAXGSzxGeCsM25tqbi6xPHDTT2fMXQFt9bR'
API_SECRET = '8t03t3Fa1GQZCD2f99r3HEE9GYVeXNhS4FyjZpCVPTbGofmoPYATilUCoXWJKixf'

# 바이낸스 선물 거래 기본 URL
BASE_URL = 'https://fapi.binance.com'


# 바이낸스 선물 시장에서 매수 주문을 위한 함수
def place_order(symbol, side, quantity, price, order_type="LIMIT"):
    # 엔드포인트 설정
    endpoint = '/fapi/v1/order'
    url = BASE_URL + endpoint

    # 타임스탬프 생성
    timestamp = int(time.time() * 1000)

    # 주문 데이터
    params = {
        'symbol': symbol,  # 거래할 코인 예시: 'BTCUSDT'
        'side': side,  # 'BUY' or 'SELL'
        'type': order_type,  # 주문 종류 (LIMIT, MARKET 등)
        'quantity': quantity,  # 수량
        'price': price,  # 가격 (지정가 주문일 경우)
        'timeInForce': 'GTC',  # Good Till Cancel (주문이 실행될 때까지 유지)
        'timestamp': timestamp
    }

    # 시크릿 키로 서명 생성 (HMAC SHA256)
    query_string = '&'.join([f"{key}={params[key]}" for key in params])
    signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    # 서명 추가
    params['signature'] = signature

    # 헤더 설정
    headers = {
        'X-MBX-APIKEY': API_KEY
    }

    # POST 요청으로 매수 주문 전송
    response = requests.post(url, headers=headers, params=params)

    # 응답 결과 출력
    return response.json()


# 매수 주문 실행 (예시)
symbol = 'BTCUSDT'  # 거래할 코인
side = 'BUY'  # 매수 주문
quantity = 0.002  # 주문 수량
price = 60000  # 지정가 주문 가격

# 주문 요청
order_result = place_order(symbol, side, quantity, price)

print(order_result)
