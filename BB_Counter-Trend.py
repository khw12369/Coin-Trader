import queue

import redis
import json
import threading
import websocket
import asyncio
import time

from ccxt import *
import ccxt
from binance.client import Client
from binance import AsyncClient, BinanceSocketManager

from collections import deque
import re

from datetime import datetime, timedelta
import logging
from logging.handlers import TimedRotatingFileHandler

import pandas as pd
import numpy as np
import sqlite3

from flask import session
import requests
import hashlib
import hmac
import os
import httpx  # ✅ 비동기 HTTP 요청을 위해 httpx 사용
import json
import urllib.parse
import platform

import asyncio

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncio
import json
import websockets
import numpy as np
import pandas as pd
from binance import AsyncClient, BinanceSocketManager
import config

class Websocket_PriceClient:
    def __init__(self, price_queue):
        self.running = False
        self.websocket = None
        self.price_queue = price_queue  # 가격 데이터 큐

    async def on_message(self, message):
        """수신된 WebSocket 메시지를 처리"""
        try:
            data = json.loads(message)

            if "k" in data:  # 캔들 데이터 확인
                await self.price_queue.put(data)  # 큐에 데이터 추가
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e} - Raw message: {message}")
        except Exception as e:
            print(f"Unexpected error in on_message: {e}")

    async def connect(self):
        """Binance WebSocket에 연결"""
        url = "wss://fstream.binance.com/ws/btcusdt@kline_1m"
        self.running = True

        while self.running:
            try:
                async with websockets.connect(url) as ws:
                    self.websocket = ws
                    print("✅ Connected to Binance Price WebSocket")

                    async for message in ws:
                        await self.on_message(message)
            except websockets.exceptions.ConnectionClosed as e:
                print(f"⚠ WebSocket closed: {e}. Reconnecting in 3s...")
                await asyncio.sleep(3)  # 3초 대기 후 재연결

    async def start(self):
        """WebSocket 시작"""
        asyncio.create_task(self.connect())

class Websocket_UserdataClient:
    def __init__(self, user_queue):
        self.running = False
        self.user_queue = user_queue  # 유저 데이터 큐
        self.api_key = config.API_KEY
        self.secret = config.API_SECRET

    async def user_datas(self):
        """Binance 유저 데이터 WebSocket 연결"""
        self.running = True
        client = await AsyncClient.create(self.api_key, self.secret)
        bm = BinanceSocketManager(client)
        ts = bm.futures_user_socket()

        async with ts as tscm:
            while self.running:
                try:
                    message = await tscm.recv()
                    await self.user_queue.put(message)  # 유저 데이터 큐에 추가
                except Exception as e:
                    print(f"Error receiving message: {e}")

    async def start(self):
        """WebSocket 시작"""
        asyncio.create_task(self.user_datas())

class TradingClient:
    def __init__(self, price_queue, user_queue):
        self.price_queue = price_queue
        self.user_queue = user_queue

        self.api_key = config.API_KEY
        self.secret = config.API_SECRET
        self.client = self.api_load()

        self.trade_data = []
        self.close = 0
        self.high = 0
        self.low = 0
        self.open = 0
        self.position_data = None
        self.traded_positions = self.get_amt()
        self.avg_price = 0
        self.pyramiding = 0
        self.atr_threthold = 0
        self.is_traded = False



    def api_load(self):
        return ccxt.binance(config={
            'apiKey': self.api_key,
            'secret': self.secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            },
        })

    async def get_available_usdt_balance(self):
        """거래소 API에서 현재 USDT 주문 가능 금액 조회"""
        try:
            balance_info = self.client.fetch_balance()
            available_usdt = balance_info['free']['USDT']  # 주문 가능 USDT 잔액
            return available_usdt
        except Exception as e:
            print(f"[❌] USDT 잔액 조회 실패: {e}")
            return 0  # 실패 시 0 반환

    async def fetch_historical_klines(self):
        """Binance API에서 과거 20개 Kline 데이터 불러오기"""
        client = await AsyncClient.create(self.api_key, self.secret)
        klines = await client.futures_klines(symbol="BTCUSDT", interval="1m", limit=200)
        await client.close_connection()

        # Kline 데이터를 trade_data 리스트에 저장
        self.trade_data = [
            {
                "symbol": "BTCUSDT",
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5])
            }
            for kline in klines
        ]
        print(f"📊 [Historical Data Fetched] Loaded {len(self.trade_data)} candles.")

    def calculate_bollinger_bands(self):
        df = pd.DataFrame(self.trade_data[-200:])

        df['MA180'] = df['close'].rolling(window=180).mean()

        df['STD180'] = df['close'].rolling(window=180).std()
        df['Upper'] = df['MA180'] + (2 * df['STD180'])
        df['Lower'] = df['MA180'] - (2 * df['STD180'])

        df['tr1'] = abs(df['high'] - df['low'])
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()

        if df.empty or df.iloc[-1].isnull().any():
            return None  # 데이터가 충분하지 않으면 None 반환
        #print(df.iloc[-1])
        return df.iloc[-2:]

    async def process_data(self):
        while True:
            try:
                price_task = asyncio.create_task(self.price_queue.get())
                user_task = asyncio.create_task(self.user_queue.get())

                done, pending = await asyncio.wait([price_task, user_task], return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    data = task.result()

                    if "e" in data and data["e"] == "kline":
                        self.close = float(data["k"]["c"])
                        self.high = float(data["k"]["h"])
                        self.low = float(data["k"]["l"])
                        self.open = float(data["k"]["o"])
                        if data["k"]["x"]:
                            candle_data = {
                                "symbol": data["s"],
                                "open": float(data["k"]["o"]),
                                "high": float(data["k"]["h"]),
                                "low": float(data["k"]["l"]),
                                "close": float(data["k"]["c"]),
                                "volume": float(data["k"]["v"])
                            }
                            self.trade_data.append(candle_data)
                            self.is_traded = False
                            if len(self.trade_data) > 200:
                                self.trade_data.pop(0)  # 리스트 크기를 30개로 제한
                            print(f"📊 [Candle Closed] {candle_data}")
                            print(f"📊 [Trade Status] amt: {self.traded_positions}, avg_pirce: {self.avg_price}, pyramiding:{self.pyramiding}, atr:{self.atr_threthold}")
                    elif data["e"] == "ORDER_TRADE_UPDATE":
                        print(f"🔔 [User Data] {data}")  # 유저 데이터 처리 추가
                        if data['o']['X'] == 'FILLED':
                            avg_price = float(data['o']['ap'])
                            amt = float(data['o']['q']) * (-1 if data['o']['S'] != 'BUY' else 1)
                            if self.traded_positions == 0 or self.traded_positions is None:
                                self.traded_positions = amt
                                self.avg_price = avg_price
                            elif self.traded_positions != 0:
                                new_amt = self.traded_positions + amt
                                if new_amt == 0:
                                    self.traded_positions = new_amt
                                    self.avg_price = 0
                                else:
                                    input_asset = self.traded_positions * self.avg_price
                                    new_asset = amt * avg_price
                                    self.traded_positions = new_amt
                                    self.avg_price = (input_asset + new_asset) / new_amt

                                #print(self.traded_positions, self.avg_price)

                await self.execute_trading_strategy()

                for task in pending:
                    task.cancel()
            except Exception as e:
                print(f"❌ Error processing data: {e}")

    async def execute_trading_strategy(self):
        if len(self.trade_data) < 200:
            await self.fetch_historical_klines()  # 과거 데이터 불러오기

        last_candle = self.trade_data[-1]
        second_candle = self.trade_data[-2]
        bb = self.calculate_bollinger_bands().reset_index(drop=True)

        last_bb = bb.iloc[0]
        second_bb = bb.iloc[1]
        self.atr_threthold = last_bb['atr'] * 2

        #vol_trend_check = last_bb['bb_diff'] < last_bb['bb_diff_median']
        crossover_check = last_candle['close'] >= last_bb['Upper'] and second_candle['close'] < second_bb['Upper']
        crossunder_check = last_candle['close'] <= last_bb['Lower'] and second_candle['close'] > second_bb['Lower']
        long_legging_check = (last_candle['close'] - last_bb['Upper']) > (last_bb['Upper'] - last_candle['open'])
        short_legging_check = (last_bb['Lower'] - last_candle['close']) > (last_candle['open'] - last_bb['Lower'])

        if not self.is_traded and self.avg_price == 0 and crossover_check and long_legging_check:
            self.position_data = {"side": "short", "entry_price": last_candle['close']}
            available_cash = await self.get_available_usdt_balance()  # USDT 주문 가능 금액 조회
            available_amt = round((float(available_cash) * 2) / last_candle['close'], 3)
            try:
                result = await self.short_open(client=self.client, coin='BTC/USDT', amt=available_amt,
                                               price=last_candle['close'], clientOrderId="BB_breakout")
                self.pyramiding += -1
                self.is_traded = True
                # if result is None:
                #    print(f"[❌] BTCUSDT: long_open() 호출 후 None 반환")
            except Exception as e:
                print(f"BTCUSDT long_open 실패: {e}")
            except:
                pass
            print("🚀 Short Position Opened")

        if not self.is_traded and self.avg_price == 0 and crossunder_check and short_legging_check:
            self.position_data = {"side": "long", "entry_price": last_candle['close']}

            available_cash = await self.get_available_usdt_balance()  # USDT 주문 가능 금액 조회
            available_amt = round((float(available_cash) * 2) / last_candle['close'], 3)
            try:
                result = await self.long_open(client=self.client, coin='BTC/USDT', amt=available_amt,
                                              price=last_candle['close'], clientOrderId="BB_breakout")
                self.pyramiding += 1
                self.is_traded = True
                # if result is None:
                #    print(f"[❌] BTCUSDT: short_open() 호출 후 None 반환")
            except Exception as e:
                print(f"BTCUSDT long_open 실패: {e}")
            except:
                pass
            print("🚀 Long Position Opened")

        if self.avg_price != 0:
            if not self.is_traded and self.pyramiding > -4 and (float(last_candle['close'])/float(self.avg_price)-1) >= 0.03 and crossover_check and long_legging_check:
                self.position_data = {"side": "short", "entry_price": last_candle['close']}

                available_cash = await self.get_available_usdt_balance()  # USDT 주문 가능 금액 조회
                available_amt = round((float(available_cash)*2) / last_candle['close'], 3)
                try:
                    result = await self.short_open(client=self.client, coin='BTC/USDT', amt=available_amt, price=last_candle['close'], clientOrderId="BB_breakout")
                    self.pyramiding += -1
                    self.is_traded = True
                    #if result is None:
                    #    print(f"[❌] BTCUSDT: long_open() 호출 후 None 반환")
                except Exception as e:
                    print(f"BTCUSDT long_open 실패: {e}")
                except:
                    pass
                print("🚀 Short Position Opened")

            if not self.is_traded and self.pyramiding < 4 and (float(self.avg_price)/float(last_candle['close'])-1) >= 0.03 and crossunder_check and short_legging_check:

                self.position_data = {"side": "long", "entry_price": last_candle['close']}

                available_cash = await self.get_available_usdt_balance()  # USDT 주문 가능 금액 조회
                available_amt = round((float(available_cash) * 2) / last_candle['close'], 3)
                try:
                    result = await self.long_open(client=self.client, coin='BTC/USDT', amt=available_amt,
                                                  price=last_candle['close'], clientOrderId="BB_breakout")
                    self.pyramiding += 1
                    self.is_traded = True
                    # if result is None:
                    #    print(f"[❌] BTCUSDT: short_open() 호출 후 None 반환")
                except Exception as e:
                    print(f"BTCUSDT long_open 실패: {e}")
                except:
                    pass
                print("🚀 Long Position Opened")

        if self.position_data and self.position_data['side'] == "short" and self.pyramiding < 0:
            #if last_candle['close'] <= bb['Upper'] and last_candle['open'] <= bb['Upper']:
            if last_candle['close'] <= last_bb['Lower']:
                print("✅ Take Profit - Closing Short Position")
                amt = (self.
                       get_amt())
                if self.traded_positions != amt:
                    self.traded_positions = amt
                #print(f"TradeReturn:{self.position_data["entry_price"] / last_candle['close'] -1}")

                try:
                    result = await self.short_close(client=self.client, coin='BTC/USDT', amt=self.traded_positions,
                                                   price=last_candle['close'], clientOrderId="BB_breakout")
                    self.pyramiding = 0
                    #if result is None:
                    #    print(f"[❌] BTCUSDT: long_close() 호출 후 None 반환")
                except Exception as e:
                    print(f"BTCUSDT long_close 실패: {e}")
                except:
                    pass

        if self.position_data and self.position_data['side'] == "long" and self.pyramiding > 0:
            #if last_candle['close'] >= bb['Lower'] and last_candle['open'] >= bb['Lower']:
            if last_candle['close'] >= last_bb['Upper']:
                amt = self.get_amt()
                if self.traded_positions != amt:
                    self.traded_positions = amt
                print("✅ Take Profit - Closing Long Position")
                #print("❌ Stop Loss - Closing Short Position")

                #print(f"TradeReturn:{self.position_data["entry_price"]/last_candle['close'] - 1}")
                try:
                    result = await self.long_close(client=self.client, coin='BTC/USDT', amt=self.traded_positions,
                                                   price=last_candle['close'], clientOrderId="BB_breakout")
                    self.pyramiding = 0
                    #if result is None:
                    #    print(f"[❌] BTCUSDT: short_close() 호출 후 None 반환")
                except Exception as e:
                    print(f"BTCUSDT short_close 실패: {e}")
                except:
                    pass



    # 요청 파라미터 설정
    def get_binance_futures_account_info(self):
        endpoint = "/fapi/v2/account"
        BASE_URL = "https://fapi.binance.com"
        url = BASE_URL + endpoint

        # 필수 파라미터 추가 (timestamp)
        params = {
            "timestamp": int(time.time() * 1000),  # 밀리초 단위 타임스탬프
            "recvWindow": 5000  # (선택 사항) 요청 유효 시간
        }

        # 서명 생성 (HMAC-SHA256)
        query_string = "&".join([f"{key}={params[key]}" for key in params])
        signature = hmac.new(self.secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature  # 서명 추가

        # 요청 헤더 설정
        headers = {
            "X-MBX-APIKEY": self.api_key  # API Key 포함
        }

        # API 호출
        response = requests.get(url, params=params, headers=headers)

        # 결과 반환
        if response.status_code == 200:
            #print(response.json())
            return response.json()
        else:
            return response.text  # 오류 메시지 반환

    def get_amt(self):
        positions = self.get_binance_futures_account_info().get("positions", [])
        btc_position = next((p['positionAmt'] for p in positions if p["symbol"] == "BTCUSDT"), None)
        #print(btc_position)
        return float(btc_position)


    async def get_max_leverage(self, symbol):
        url = "https://fapi.binance.com/fapi/v1/leverageBracket"
        headers = {'X-MBX-APIKEY': self.api_key}
        timestamp = await self.get_server_time()  # 서버 시간 가져오기

        if timestamp is None:
            self.logger.error("서버 시간 정보를 가져올 수 없습니다.")
            return None

        # 1️⃣ 요청 파라미터 생성
        params = {
            "symbol": symbol,
            "timestamp": timestamp
        }

        # 2️⃣ Query String 생성
        query_string = urllib.parse.urlencode(params)

        # 3️⃣ HMAC SHA256 서명 생성
        signature = hmac.new(self.secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature  # 서명 추가

        try:
            # 4️⃣ 요청 전송 (서명 포함)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)

            # 5️⃣ 응답 JSON 파싱
            try:
                data = response.json()
            except Exception as e:
                self.logger.error(f"JSON 파싱 오류: {e}, 응답 내용: {response.text}")
                return None

            #print("API 응답:", data)  # 디버깅을 위한 출력

            # 6️⃣ 응답이 리스트인지 확인
            if isinstance(data, dict) and "code" in data:
                self.logger.error(f"API 오류 발생: {data}")
                return None

            if not isinstance(data, list):
                self.logger.error(f"API 응답이 리스트가 아님: {data}")
                return None

            # 7️⃣ 최대 레버리지 찾기
            for bracket in data:
                if bracket.get('symbol') == symbol:
                    return max([int(br['initialLeverage']) for br in bracket.get('brackets', [])])

            return None

        except httpx.HTTPStatusError as http_err:
            self.logger.error(f"HTTP 오류: {http_err}")
            return None
        except Exception as e:
            self.logger.error(f"예상치 못한 오류 발생: {e}")
            return None

    async def get_server_time(self):
        BASE_URL = "https://fapi.binance.com"
        url = f"{BASE_URL}/fapi/v1/time"
        response = requests.get(url)
        return response.json()['serverTime']

    # 사용자가 입력한 레버리지와 비교하여 최소값을 설정
    async def set_leverage(self, symbol, user_leverage):
        max_leverage = await self.get_max_leverage(symbol)

        if max_leverage is None:
            self.logger.error(f"{symbol}의 최대 레버리지를 가져올 수 없습니다.")
            return

        leverage_to_set = min(max_leverage, user_leverage)
        timestamp = await self.get_server_time()
        params = {"symbol": symbol, "leverage": leverage_to_set, "timestamp": timestamp}

        query_string = '&'.join([f"{key}={params[key]}" for key in params])
        signature = hmac.new(self.secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        params['signature'] = signature

        async with httpx.AsyncClient() as client:
            await client.post("https://fapi.binance.com/fapi/v1/leverage", headers={'X-MBX-APIKEY': self.api_key},
                              params=params)

    async def long_open(self, client, coin, amt=None, price=None, clientOrderId=None):
        params = {}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId
        #await self.set_leverage(coin.replace('/', ''), 20)

        if price is not None:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='limit', side='buy', amount=amt,
                                    price=price, params=params)
        else:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='market', side='buy', amount=amt,
                                    params=params)

    async def short_open(self, client, coin, amt=None, price=None, clientOrderId=None):
        params = {}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId
        #await self.set_leverage(coin.replace('/', ''), 20)

        if price is not None:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='limit', side='sell', amount=float(amt),
                                    price=price, params=params)
        else:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='market', side='sell', amount=float(amt),
                                    params=params)

    async def long_close(self, client, coin, amt=None, price=None, clientOrderId=None):
        params = {'reduceOnly': True}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId
        if price is not None:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='limit', side='sell', amount=float(amt),
                                    price=price, params=params)
        else:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='market', side='sell', amount=float(amt),
                                    params=params)

    async def short_close(self, client, coin, amt=None, price=None, clientOrderId=None):
        params = {'reduceOnly': True}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId
        if price is not None:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='limit', side='buy', amount=-float(amt),
                                    price=price, params=params)
        else:
            await asyncio.to_thread(binance.create_order, client, symbol=coin, type='market', side='buy', amount=-float(amt),
                                    params=params)

async def main():
    price_queue = asyncio.Queue()
    user_queue = asyncio.Queue()
    candle_client = Websocket_PriceClient(price_queue)
    userdata_client = Websocket_UserdataClient(user_queue)
    trading_client = TradingClient(price_queue, user_queue)
    await candle_client.start()
    await userdata_client.start()
    asyncio.create_task(trading_client.process_data())
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())