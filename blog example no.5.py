import requests
import time
import hmac
import hashlib
import re

# 바이낸스 API 키와 시크릿 키
API_KEY = 'HgoM8YxJ5DZwJXaVRZ87JEEeGpmWDSAXGSzxGeCsM25tqbi6xPHDTT2fMXQFt9bR'
API_SECRET = '8t03t3Fa1GQZCD2f99r3HEE9GYVeXNhS4FyjZpCVPTbGofmoPYATilUCoXWJKixf'


def validate_client_order_id(client_order_id):
    """Validate the client order ID against the specified regex."""
    pattern = r'^[\.A-Z\:/a-z0-9_-]{1,36}$'

    if client_order_id is not None:
        if re.match(pattern, client_order_id):
            return client_order_id  # Return the valid client order ID
        else:
            # print("clientID error")  # Print error message for invalid ID
            return None  # Optionally return None to indicate an invalid ID

def place_order(symbol, side, quantity, price, order_type="LIMIT", reduceOnly=None, client_ID=None):
    # 엔드포인트 설정
    endpoint = '/fapi/v1/order'
    url = 'https://fapi.binance.com' + endpoint

    API_KEY = 'HgoM8YxJ5DZwJXaVRZ87JEEeGpmWDSAXGSzxGeCsM25tqbi6xPHDTT2fMXQFt9bR'
    API_SECRET = '8t03t3Fa1GQZCD2f99r3HEE9GYVeXNhS4FyjZpCVPTbGofmoPYATilUCoXWJKixf'

    # 타임스탬프 생성
    timestamp = int(time.time() * 1000)

    order_id = validate_client_order_id(client_ID)

    # 주문 데이터
    params = {
        'symbol': symbol,  # 거래할 코인 예시: 'BTCUSDT'
        'side': side,  # 'BUY' or 'SELL'
        'type': order_type,  # 주문 종류 (LIMIT, MARKET 등)
        'quantity': quantity,  # 수량
        #'price': price,  # 가격 (지정가 주문일 경우)
        #'timeInForce': 'GTC',  # Good Till Cancel (주문이 실행될 때까지 유지)
        'timestamp': timestamp
    }

    if order_type == "LIMIT":
        params['price'] = price
        params['quantity'] = quantity
        params['timeInForce'] = 'GTC'  # Good Till Cancel

        # 시장가 주문의 경우, 가격을 제외하고 수량만 필요
    elif order_type == "MARKET":
        params['quantity'] = quantity

        # client_ID가 있는 경우에만 newClientOrderId 파라미터 추가
    if client_ID:
        params['newClientOrderId'] = client_ID

        # reduceOnly가 있는 경우에만 reduceOnly 파라미터 추가
    if reduceOnly is not None:
        params['reduceOnly'] = reduceOnly

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
    if response.status_code == 200:
        return response.json()  # 성공시 JSON 응답 반환
    else:
        # 에러일 경우 상태 코드와 에러 메시지 출력
        error_message = response.json()
        print(f"Error {response.status_code}: {error_message}")
        return {"error": response.status_code, "message": error_message}

symbol = 'BTCUSDT'  # 거래할 코인
side = 'BUY'  # 매수 주문
quantity = 0.002  # 주문 수량
price = 60000  # 지정가 주문 가격
client_ID = 'strategy_v2'
reduceOnly = True
# 주문 요청
order_result = place_order(symbol=symbol, side=side, quantity=quantity, order_type="LIMIT", price=price, client_ID=client_ID)

print(order_result)