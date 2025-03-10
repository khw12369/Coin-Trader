import asyncio
from binance import AsyncClient, BinanceSocketManager


class UserDatas():

    def __init__(self):

        self.updates = dict()

    def run(self):
        # 비동기 루프 실행
        asyncio.run(self.user_datas())

    async def user_datas(self):
        api_key = "<YOUR_API_KEY>"
        api_secret = "<YOUR_API_SECRET>"
        # 비동기 클라이언트 생성
        client = await AsyncClient.create(api_key, api_secret)
        bm = BinanceSocketManager(client)

        # 선물 계정의 유저 소켓을 연결
        ts = bm.futures_user_socket()

        # 소켓 연결 후 메시지를 수신
        async with ts as tscm:
            while True:
                self.updates = await tscm.recv()  # 메시지 수신
                print("Received update:", self.updates)

        # 클라이언트 종료
        await client.close_connection()

if __name__ == "__main__":
    # UserDatas 클래스의 인스턴스를 생성하고 run 메서드 실행
    user_data_instance = UserDatas()
    user_data_instance.run()