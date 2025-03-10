from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

# 바이낸스 API 키와 시크릿 키 설정
api_key = 'HgoM8YxJ5DZwJXaVRZ87JEEeGpmWDSAXGSzxGeCsM25tqbi6xPHDTT2fMXQFt9bR'
api_secret = '8t03t3Fa1GQZCD2f99r3HEE9GYVeXNhS4FyjZpCVPTbGofmoPYATilUCoXWJKixf'


# 클라이언트 초기화
client = Client(api_key, api_secret)

# 사용 예시: 현물에서 선물로 USDT 이체
transfer1 = client.make_universal_transfer(type="MAIN_UMFUTURE", asset="USDT", amount="100")


# 사용 예시: 선물에서 현물로 USDT 이체
transfer2 = client.make_universal_transfer(type="UMFUTURE_MAIN", asset="USDT", amount="100")
