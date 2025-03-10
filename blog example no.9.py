import ccxt
import config
import pprint

def api_load():
    return ccxt.binance(config={
        'apiKey': config.API_KEY,
        'secret': config.API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
        },
    })




def api_call_to_get_balance():
    return ccxt.binanceus.fetch_balance(api_load(), params={"type": "future", 'recvWindow': 10000000})

binance = api_load()

try:
    # 시장 데이터 로드
    markets = binance.load_markets()
    balance = binance.fetch_balance({'type': 'future'})  # 선물 계정의 포지션 정보
    positions = balance['info']['positions']

    print(positions)

except ccxt.BaseError as e:
    print(f"에러 발생: {str(e)}")
