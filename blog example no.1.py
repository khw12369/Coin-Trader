import asyncio
import websockets
import json
import requests

# Binance Futures API URL
BASE_URL = "https://fapi.binance.com"

# Kline interval (1m, 5m, 1h, etc.)
KLINE_INTERVAL = "1m"


async def get_all_symbols():
    """
    Binance Futures에 상장된 모든 심볼을 가져옵니다.
    """
    endpoint = "/fapi/v1/exchangeInfo"
    response = requests.get(BASE_URL + endpoint)
    data = response.json()

    # 선물 시장에서 사용 가능한 모든 심볼 추출
    symbols = [item['symbol'].lower() for item in data['symbols']]
    tickerlist = [symbols[i] for i in range(len(symbols)) if symbols[i][-4:] == 'usdt']
    return tickerlist


async def subscribe_to_kline(symbols):
    """
    여러 심볼에 대해 Kline 데이터를 WebSocket으로 수신합니다.
    """
    # WebSocket URL
    ws_url = f"wss://fstream.binance.com/stream?streams="
    streams = [f"{symbol}@kline_{KLINE_INTERVAL}" for symbol in symbols]
    ws_url += '/'.join(streams)

    # WebSocket 연결 및 메시지 수신
    async with websockets.connect(ws_url) as websocket:
        print("WebSocket connected!")
        try:
            while True:
                data = await websocket.recv()
                kline_data = json.loads(data)

                # 받은 데이터를 원하는 형식으로 처리합니다.
                handle_kline_data(kline_data)
        except websockets.ConnectionClosed:
            print("WebSocket connection closed, reconnecting...")
            await subscribe_to_kline(symbols)


def handle_kline_data(data):
    """
    수신된 Kline 데이터를 처리하는 함수.
    필요한 작업(예: 데이터 저장, 로그 출력 등)을 이곳에서 수행합니다.
    """
    # 데이터 예시 출력
    print(data)


async def main():
    # 모든 심볼 가져오기
    symbols = await get_all_symbols()
    print(f"Subscribed to {len(symbols)} symbols.")

    # Kline 데이터 수신 시작
    await subscribe_to_kline(symbols)


if __name__ == "__main__":
    # 비동기 루프 실행
    asyncio.run(main())