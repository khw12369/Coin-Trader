from binance.client import Client
import config
from binance.exceptions import BinanceAPIException, BinanceOrderException

# 바이낸스 API 키와 시크릿 키 설정
API_KEY = config.API_KEY
API_SECRET = config.API_SECRET


# 클라이언트 초기화
client = Client(API_KEY, API_SECRET)

# 사용 예시: 현물에서 선물로 USDT 이체
transfer1 = client.make_universal_transfer(type="MAIN_UMFUTURE", asset="USDT", amount="100")


# 사용 예시: 선물에서 현물로 USDT 이체
transfer2 = client.make_universal_transfer(type="UMFUTURE_MAIN", asset="USDT", amount="100")
