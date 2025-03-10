#import ssl
from ccxt import *
import ccxt
from binance.client import Client
from binance import AsyncClient, BinanceSocketManager
import pandas as pd
import openpyxl
import sqlite3
import queue
import telegram
from datetime import datetime, time, timedelta


from PyQt5.QtCore import *
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QDateTime, QTime, QEventLoop
from PyQt5.QtGui import QColor
from qasync import QEventLoop, asyncSlot

import sys
import os
import ctypes
import logging
from logging.handlers import TimedRotatingFileHandler
from concurrent.futures import ThreadPoolExecutor

from collections import deque
import threading
import websocket
import websockets
import requests
import json
import asyncio
import requests
import time
import hashlib
import hmac
import config

def exception_hook(exctype, value, traceback):
    # Print the error information
    sys.__excepthook__(exctype, value, traceback)
    sys.exit(1)

def suppress_qt_warnings():
    os.environ["QT_DEVICE_PIXEL_RATIO"] = "0"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"

def resource_path(*relative_Path_AND_File):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = getattr(
            sys,
            '_MEIPASS',
            os.path.dirname(os.path.abspath(__file__))
        )
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, *relative_Path_AND_File)

if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys._execpthook = sys.excepthook
sys.excepthook = exception_hook

form = resource_path("coin-bot_UI_v7.ui")  # UI파일 입력
form_class = uic.loadUiType(form)[0]

# Prevent sleep mode
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)

class websocket_kline_v1(QThread):
    date_received = pyqtSignal(dict)
    connections_updated = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

        websocket.enableTrace(False)

        binance_futures = ccxt.binance(config={
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            },
        })
        ticker = list(binance_futures.fetch_tickers().keys())
        tickerlist = [ticker[i][:-5] for i in range(len(ticker)) if ticker[i][-4:] == 'USDT']

        self.converted_tickerlist = [ticker.replace('/', '').lower() for ticker in tickerlist]
        # self.converted_tickerlist = ['xrpusdt']
        url = "wss://fstream.binance.com/ws?"
        # self.WS = websocket.WebSocketApp(url, on_open=self.on_open, on_message=self.on_message)
        self.data = dict()
        self.websocket_instances = {}

    def create_socket(self, symbols_chunk, chunk_id):
        def on_open(ws):
            for symbol in symbols_chunk:
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol}@kline_1m"],
                    "id": 1
                }
                ws.send(json.dumps(subscribe_message))

                print(symbol)
                time.sleep(0.5)  # To respect the 5 messages per second limit
            self.connections_updated.emit(len(self.websocket_instances))

        def on_error(ws, error):
            error_message = f"Websocket error: {error}"
            print(error_message)  # Print error for debugging

        def on_close(ws, close_status_code, close_msg):
            print(f"Connection closed with status {close_status_code}, message: {close_msg}")
            print("Attempting to reconnect...")
            time.sleep(10)  # Wait for 10 seconds before attempting to reconnect
            self.create_socket(symbols_chunk, chunk_id)  # Call a function to reconnect without creating a new thread
            self.connections_updated.emit(len(self.websocket_instances))

        def on_pong(ws, payload):
            print("Pong received:", payload)

        def connect_and_run():
            socket = "wss://fstream.binance.com/ws?"
            ws = websocket.WebSocketApp(socket,
                                        on_open=on_open,
                                        on_close=on_close,
                                        on_error=on_error,
                                        on_message=self.on_message,
                                        on_pong=on_pong)
            self.websocket_instances[chunk_id] = ws
            ws.run_forever(ping_interval=60, ping_timeout=180)
            # ws.run_forever()

        connect_and_run()

        # subscribe_message = {"method": "SUBSCRIBE", "params": ["btcusdt@kline_1m", "ethusdt@kline_1m"], "id": 1}
        # ws.send(json.dumps(subscribe_message))
        # sub_msg = {"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}

    def on_message(self, ws, message):
        self.data = json.loads(message)
        # print(self.data)
        self.date_received.emit(self.data)

    def run(self):
        chunk_size = 50  # Adjust as needed
        chunks = [self.converted_tickerlist[i:i + chunk_size] for i in
                  range(0, len(self.converted_tickerlist), chunk_size)]

        threads = []
        for i, chunk in enumerate(chunks):
            t = threading.Thread(target=self.create_socket, args=(chunk, i))
            t.start()
            threads.append(t)
            time.sleep(1)

        for thread in threads:
            thread.join()

class websocket_depth(QThread):
    depth_received = pyqtSignal(dict)
    connections_updated = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

        websocket.enableTrace(False)

        binance_futures = ccxt.binance(config={
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            },
        })
        ticker = list(binance_futures.fetch_tickers().keys())
        tickerlist = [ticker[i][:-5] for i in range(len(ticker)) if ticker[i][-4:] == 'USDT']

        self.converted_tickerlist = [ticker.replace('/', '').lower() for ticker in tickerlist]
        # self.converted_tickerlist = ['xrpusdt']
        url = "wss://fstream.binance.com/ws?"
        # self.WS = websocket.WebSocketApp(url, on_open=self.on_open, on_message=self.on_message)
        self.data = dict()
        self.websocket_instances = {}

    def create_socket(self, symbols_chunk, chunk_id):
        def on_open(ws):
            for symbol in symbols_chunk:
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol}@depth"],
                    "id": 1
                }
                ws.send(json.dumps(subscribe_message))

                print(symbol)
                time.sleep(0.5)  # To respect the 5 messages per second limit
            #self.connections_updated.emit(len(self.websocket_instances))

        def on_error(ws, error):
            error_message = f"Websocket error: {error}"
            print(error_message)  # Print error for debugging

        def on_close(ws, close_status_code, close_msg):
            print(f"Connection closed with status {close_status_code}, message: {close_msg}")
            print("Attempting to reconnect...")
            time.sleep(10)  # Wait for 10 seconds before attempting to reconnect
            self.create_socket(symbols_chunk, chunk_id)  # Call a function to reconnect without creating a new thread
            self.connections_updated.emit(len(self.websocket_instances))

        def on_pong(ws, payload):
            print("Pong received:", payload)

        def connect_and_run():
            socket = "wss://fstream.binance.com/ws?"
            ws = websocket.WebSocketApp(socket,
                                        on_open=on_open,
                                        on_close=on_close,
                                        on_error=on_error,
                                        on_message=self.on_message,
                                        on_pong=on_pong)
            self.websocket_instances[chunk_id] = ws
            ws.run_forever(ping_interval=60, ping_timeout=180)
            # ws.run_forever()

        connect_and_run()

        # subscribe_message = {"method": "SUBSCRIBE", "params": ["btcusdt@kline_1m", "ethusdt@kline_1m"], "id": 1}
        # ws.send(json.dumps(subscribe_message))
        # sub_msg = {"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}

    def on_message(self, ws, message):
        self.data = json.loads(message)
        # print(self.data)
        self.depth_received.emit(self.data)

    def run(self):
        chunk_size = 50  # Adjust as needed
        chunks = [self.converted_tickerlist[i:i + chunk_size] for i in
                  range(0, len(self.converted_tickerlist), chunk_size)]

        threads = []
        for i, chunk in enumerate(chunks):
            t = threading.Thread(target=self.create_socket, args=(chunk, i))
            t.start()
            threads.append(t)
            time.sleep(1)

        for thread in threads:
            thread.join()

class user_datas(QThread):
    update_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        # super(ListenWebsocket, self).__init__(parent)
        super().__init__(parent)

        self.parent = parent
        self.updates = dict()
        # self.loop = asyncio.get_event_loop()

    def run(self):
        self.parent.evnet_control_loop.run_until_complete(self.user_datas())

    async def user_datas(self):
        api_key = config.API_KEY
        api_secret = config.API_SECRET
        client = await AsyncClient.create(api_key, api_secret)
        bm = BinanceSocketManager(client)
        # start any sockets here, i.e a trade socket
        # ts = bm.user_socket()
        ts = bm.futures_user_socket()

        # then start receiving messages
        async with ts as tscm:
            while True:
                self.updates = await tscm.recv()
                self.update_received.emit(self.updates)

class websocket_combine_kline(QThread):
    kline_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

        #websocket.enableTrace(False)

        binance_futures = ccxt.binance(config={
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            },
        })
        ticker = list(binance_futures.fetch_tickers().keys())
        tickerlist = [ticker[i][:-5] for i in range(len(ticker)) if ticker[i][-4:] == 'USDT']

        self.converted_tickerlist = [ticker.replace('/', '').lower() for ticker in tickerlist if ticker.replace('/', '').lower() != 'usdcusdt']

        self.data = dict()

        #logging.basicConfig(filename='websocket_log.log', level=logging.INFO)
        self.setup_logger()

    def setup_logger(self):
        self.logger = logging.getLogger("websocket_log")
        self.logger.setLevel(logging.INFO)

        # 기존 핸들러 제거
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        handler = TimedRotatingFileHandler(
            filename='websocket_log.log',
            when='H',
            interval=1,
            backupCount=0,
            encoding='utf-8'  # 인코딩을 UTF-8로 설정
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    #def run(self):
    #    asyncio.run(self.main())

    def run(self):
        try:
            # 현재 실행 중인 이벤트 루프가 있는지 확인
            loop = asyncio.get_running_loop()
            # 실행 중인 이벤트 루프가 있다면 해당 루프에서 비동기 작업 실행
            #print("An event loop is already running. Using it...")
            loop.create_task(self.main())
        except RuntimeError:
            # 실행 중인 이벤트 루프가 없다면 새 이벤트 루프 생성
            #print("No event loop is running. Creating a new one...")
            asyncio.run(self.main())  # 새 이벤트 루프에서 실행

    def split_list(self, lst, n):
        return [lst[i:i + n] for i in range(0, len(lst), n)]

    # 스트림 URL 생성 함수
    def create_stream_url(self, tickers):
        return "wss://fstream.binance.com/stream?streams=" + "/".join([f"{ticker}@kline_1m" for ticker in tickers])

    # 웹소켓 메시지 핸들링 함수
    async def handle_messages(self, websocket):
        async for message in websocket:
            data = json.loads(message)
            self.kline_received.emit(data)

    #연결 로그 기록 함수
    async def log_every_10_minutes(self):
        while True:
            self.logger.info(f"Logging at {datetime.now()}")
            await asyncio.sleep(600)  # 600초 = 10분

    # 웹소켓 연결 함수
    async def connect_websocket(self, tickers_chunk):
        url = self.create_stream_url(tickers_chunk)
        #async with websockets.connect(url, ping_interval=180, ping_timeout=600) as websocket:
        #    await self.handle_messages(websocket)
        try:
            async with websockets.connect(url, ping_interval=30, ping_timeout=60) as websocket:
                await self.handle_messages(websocket)
        except (websockets.ConnectionClosedError, websockets.InvalidStatusCode, asyncio.TimeoutError) as e:
            self.logger.error(f"WebSocket connection error: {e}. Reconnecting...")
            await asyncio.sleep(5)  # 잠시 대기 후 재연결
            await self.connect_websocket(tickers_chunk)

    # 메인 비동기 함수
    async def main(self):
        # 티커 리스트를 200개씩 나누기
        chunks = self.split_list(self.converted_tickerlist, 300)

        # 비동기 웹소켓 연결 작업
        tasks = [self.connect_websocket(chunk) for chunk in chunks]
        #tasks.append(self.log_every_10_minutes())
        await asyncio.gather(*tasks)

class websocket_combine_8hr(QThread):
    price_8hr_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

        #websocket.enableTrace(False)

        binance_futures = ccxt.binance(config={
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            },
        })
        ticker = list(binance_futures.fetch_tickers().keys())
        tickerlist = [ticker[i][:-5] for i in range(len(ticker)) if ticker[i][-4:] == 'USDT']

        self.converted_tickerlist = [ticker.replace('/', '').lower() for ticker in tickerlist if ticker.replace('/', '').lower() != 'usdcusdt']

        self.data = dict()

        #logging.basicConfig(filename='websocket_log_depth.log', level=logging.INFO)
        #self.setup_logger()

    def setup_logger(self):
        self.logger = logging.getLogger("websocket_log")
        self.logger.setLevel(logging.INFO)

        # 기존 핸들러 제거
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        handler = TimedRotatingFileHandler(
            filename='websocket_log.log',
            when='H',
            interval=1,
            backupCount=0,
            encoding='utf-8'  # 인코딩을 UTF-8로 설정
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def run(self):
        asyncio.run(self.main())

    def split_list(self, lst, n):
        return [lst[i:i + n] for i in range(0, len(lst), n)]

    # 스트림 URL 생성 함수
    def create_stream_url(self, tickers):
        return "wss://fstream.binance.com/stream?streams=" + "/".join([f"{ticker}@kline_4h" for ticker in tickers])
        #return "wss://stream.binance.com:9443/stream?streams=" + "/".join([f"{ticker}@depth" for ticker in tickers])

    # 웹소켓 메시지 핸들링 함수
    async def handle_messages(self, websocket):
        async for message in websocket:
            data = json.loads(message)
            self.price_8hr_received.emit(data)

        # 10분마다 로그 기록 함수
    async def log_every_10_minutes(self):
        while True:
            self.logger.info(f"Logging at {datetime.now()}")
            await asyncio.sleep(600)  # 600초 = 10분

    # 웹소켓 연결 함수
    async def connect_websocket(self, tickers_chunk):
        url = self.create_stream_url(tickers_chunk)
        async with websockets.connect(url) as websocket:
            await self.handle_messages(websocket)

    # 메인 비동기 함수
    async def main(self):
        # 티커 리스트를 200개씩 나누기
        chunks = self.split_list(self.converted_tickerlist, 200)

        # 비동기 웹소켓 연결 작업
        tasks = [self.connect_websocket(chunk) for chunk in chunks]
        #tasks.append(self.log_every_10_minutes())
        await asyncio.gather(*tasks)

class websocket_combine_24hticker(QThread):
    vol24_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

        websocket.enableTrace(False)

        binance_futures = ccxt.binance(config={
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            },
        })
        ticker = list(binance_futures.fetch_tickers().keys())
        tickerlist = [ticker[i][:-5] for i in range(len(ticker)) if ticker[i][-4:] == 'USDT']

        self.converted_tickerlist = [ticker.replace('/', '').lower() for ticker in tickerlist if ticker.replace('/', '').lower() != 'usdcusdt']

        self.data = dict()

        #logging.basicConfig(filename='websocket_log_depth.log', level=logging.INFO)
        self.setup_logger()

    def setup_logger(self):
        self.logger = logging.getLogger("websocket_log")
        self.logger.setLevel(logging.INFO)

        # 기존 핸들러 제거
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        handler = TimedRotatingFileHandler(
            filename='websocket_log.log',
            when='H',
            interval=1,
            backupCount=0,
            encoding='utf-8'  # 인코딩을 UTF-8로 설정
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def run(self):
        asyncio.run(self.main())

    def split_list(self, lst, n):
        return [lst[i:i + n] for i in range(0, len(lst), n)]

    # 스트림 URL 생성 함수
    def create_stream_url(self, tickers):
        return "wss://fstream.binance.com/stream?streams=" + "/".join([f"{ticker}@ticker" for ticker in tickers])
        #return "wss://stream.binance.com:9443/stream?streams=" + "/".join([f"{ticker}@depth" for ticker in tickers])

    # 웹소켓 메시지 핸들링 함수
    async def handle_messages(self, websocket):
        async for message in websocket:
            data = json.loads(message)
            self.vol24_received.emit(data)

        # 10분마다 로그 기록 함수
    async def log_every_10_minutes(self):
        while True:
            self.logger.info(f"Logging at {datetime.now()}")
            await asyncio.sleep(600)  # 600초 = 10분

    # 웹소켓 연결 함수
    async def connect_websocket(self, tickers_chunk):
        url = self.create_stream_url(tickers_chunk)
        async with websockets.connect(url) as websocket:
            await self.handle_messages(websocket)

    # 메인 비동기 함수
    async def main(self):
        # 티커 리스트를 200개씩 나누기
        chunks = self.split_list(self.converted_tickerlist, 200)

        # 비동기 웹소켓 연결 작업
        tasks = [self.connect_websocket(chunk) for chunk in chunks]
        #tasks.append(self.log_every_10_minutes())
        await asyncio.gather(*tasks)

class MainDialog(QMainWindow, form_class):

    def __init__(self):
        super().__init__()

        self.setupUi(self)

        self.position_loop = asyncio.get_event_loop()
        self.evnet_control_loop = asyncio.get_event_loop()
        self.position_update_loop = QEventLoop()

        self.db_buffer = queue.Queue()
        #self.db_queue = asyncio.Queue()  # ✅ 비동기 DB 저장용 Queue 추가
        #self.db_task = None  # ✅ 별도의 비동기 Task 실행

        self.binance_futures = self.api_load()

        self.client = self.api_load()
        self._cached_balance = None
        self.update_balance_cache()
        # self.timer_for_websocket_kline_v1 = QTimer(self)
        tickers = list(self.binance_futures.fetch_tickers().keys())
        self.tickerlist = [tickers[i][:-5] for i in range(len(tickers)) if tickers[i][-4:] == 'USDT']
        self.converted_tickerlist = [ticker.replace('/', '') for ticker in self.tickerlist if ticker.replace('/', '') != 'USDCUSDT']

        self.period = 5
        self.recent_prices = {symbol: deque(maxlen=self.period) for symbol in self.converted_tickerlist}

        self.cp = {symbol: None for symbol in self.converted_tickerlist}
        self.previous_n = {symbol: None for symbol in self.converted_tickerlist}
        self.present_n = {symbol: None for symbol in self.converted_tickerlist}
        self.cul_n = {symbol: deque(maxlen=20) for symbol in self.converted_tickerlist}
        self.ohlc = {symbol: {
            'open': deque(maxlen=5),
            'high': deque(maxlen=5),
            'low': deque(maxlen=5),
            'close': deque(maxlen=5)
        } for symbol in self.converted_tickerlist}

        self.close_8hr = {symbol: None for symbol in self.converted_tickerlist}
        self.open_8hr = {symbol: None for symbol in self.converted_tickerlist}
        self.high_8hr = {symbol: None for symbol in self.converted_tickerlist}
        self.low_8hr = {symbol: None for symbol in self.converted_tickerlist}

        self.candles_8hr_ticker = {symbol: None for symbol in self.converted_tickerlist}
        self.vol_rate_from_low = None  # 마지막 vol-rate 순위 저장
        self.vol_rate_from_high = None

        columns = ['Timestamp', 'Ticker', 'Current Price', 'Open Price', 'Prev High', 'Prev Low', 'Noise']
        self.df_for_log = pd.DataFrame(columns=columns)

        self.ma = {symbol: None for symbol in self.converted_tickerlist}
        self.vol = {symbol: None for symbol in self.converted_tickerlist}
        self.bids = {symbol: None for symbol in self.converted_tickerlist}
        self.asks = {symbol: None for symbol in self.converted_tickerlist}

        self.positions = {symbol: 0 for symbol in self.converted_tickerlist}
        self.position_prices = {symbol: None for symbol in self.converted_tickerlist}
        self.loss_cut_time = {symbol: None for symbol in self.converted_tickerlist}

        self.orb_positions = {symbol: 0 for symbol in self.converted_tickerlist}
        self.orb_position_prices = {symbol: None for symbol in self.converted_tickerlist}

        self.timezone_A = [1, 2, 3, 4, 9, 10, 11, 12, 17, 18, 19, 20]
        self.timezone_B = [5, 6, 7, 8, 13, 14, 15, 16, 21, 22, 23, 0]

        self.position_A = {symbol: 0 for symbol in self.converted_tickerlist}
        self.position_B = {symbol: 0 for symbol in self.converted_tickerlist}

        self.breakout_positions = {symbol: 0 for symbol in self.converted_tickerlist}
        self.order_opened = {symbol: False for symbol in self.converted_tickerlist}
        self.breakout_position_prices = {symbol: None for symbol in self.converted_tickerlist}
        self.breakout_pnl = {symbol: 0 for symbol in self.converted_tickerlist}

        self.profit_realized = 0
        self.loss_realized = 0
        self.reset_operating = True
        if self.reset_operating:
            self.reset_check.setStyleSheet("background-color: darkblue; color: white;")

        self.orb_candle_30m = {symbol: [None, None, None, None] for symbol in self.converted_tickerlist}

        self.open_range = {symbol: None for symbol in self.converted_tickerlist}
        self.orb_long_target = {symbol: None for symbol in self.converted_tickerlist}
        self.orb_short_target = {symbol: None for symbol in self.converted_tickerlist}
        self.orb_signal_times = {symbol: [None, None, None] for symbol in self.converted_tickerlist}

        self.signal_times = {symbol: [None, None, None] for symbol in self.converted_tickerlist}

        self.candle_8h = {symbol: [None, None, None, None] for symbol in self.converted_tickerlist}
        #self.positions_times = {symbol: None for symbol in self.converted_tickerlist}
        self.pyramidings = {symbol: float(0) for symbol in self.converted_tickerlist}

        self.is_running = False
        self.is_searching = False
        self.start_process = True
        self.last_executed = None  # 마지막으로 실행된 시간을 추적하는 변수
        self.loop = None

        self.setup_logger()

        # 환경설정
        ###########################################################################################################
        # 운영

        self.worker3 = user_datas(self)
        #self.combine_kline = websocket_combine_kline(self)
        self.price_8hrs = websocket_combine_8hr(self)

        self.worker3.start()
        self.worker3.update_received.connect(self.handle_position)
        QApplication.processEvents()

        #self.combine_kline.start()
        #self.combine_kline.kline_received.connect(self.handle_price)

        self.price_8hrs.start()
        self.price_8hrs.price_8hr_received.connect(self.handle_price_8hr)

        for ticker in self.converted_tickerlist:
            self.get_8hr_candle(ticker)

        #self.contiue_all_position()
        self.load_positions_from_db()
        #self.contiue_all_position()
        #self.rank_last_vol_rate()

        self.run_strategy.clicked.connect(self.toggle_main)
        QApplication.processEvents()

        self.searchButton.clicked.connect(self.toggle_search)
        QApplication.processEvents()

        self.reset_check.clicked.connect(self.toggle_resetcheck)
        QApplication.processEvents()

        self.export_button.clicked.connect(self.save_to_excel_if_needed)  # 클릭 이벤트 연결
        QApplication.processEvents()

        #for ticker in self.converted_tickerlist:
            #print(self._cached_balance['info']['positions'])
            #self.positions[ticker] = float(self._cached_balance['info']['positions'][self.list_num(ticker)]['positionAmt'])

        #####################################################################################################################
        #테스트

        #####################################################################################################################

    def handle_price_8hr(self, data):
        data_symbol = data['data'].get('s', '')
        if data['data'].get('k'):
            self.close_8hr[data_symbol] = float(data['data']['k']['c']) if data['data']['k']['c'] else self.close_8hr[data_symbol]
            self.open_8hr[data_symbol] = float(data['data']['k']['o']) if data['data']['k']['o'] else self.open_8hr[data_symbol]
            self.high_8hr[data_symbol] = float(data['data']['k']['h']) if data['data']['k']['h'] else self.high_8hr[data_symbol]
            self.low_8hr[data_symbol] = float(data['data']['k']['l']) if data['data']['k']['l'] else self.low_8hr[data_symbol]

        #if str(data['data']['k']['x']) == 'True':
        #    self.update_8hr_candle(data_symbol, float(data['data']['k']['o']), float(data['data']['k']['h']), float(data['data']['k']['l']), float(data['data']['k']['c']))

    def rank_last_vol_rate(self):
        # 모든 티커의 마지막 vol-rate 값을 추출
        last_vol_rates = {}
        for ticker, df in self.candles_8hr_ticker.items():
            if df.empty:
                pass
            else:
                last_vol_rates[ticker] = df['vol-rate'].iloc[-1]
        #last_vol_rates = {ticker: df['vol-rate'].iloc[-1] for ticker, df in self.candles_8hr_ticker.items()}

        # pandas.Series로 변환 후 순위 계산
        vol_rate_series = pd.Series(last_vol_rates)
        vol_rate_from_high = vol_rate_series.rank(ascending=False)
        self.vol_rate_from_high = vol_rate_from_high.sort_values()[:50]
        filtered_vol_rate_series = vol_rate_series[vol_rate_series <= 1.5]
        vol_rate_rank_from_low = filtered_vol_rate_series.rank(ascending=True)  # 높은 값이 높은 순위
        self.vol_rate_from_low = vol_rate_rank_from_low.sort_values()[:50]
        #print(self.vol_rate_from_low)

    def get_8hr_candle(self, ticker):

        candles = ccxt.binanceus.fetch_ohlcv(self.client, symbol=ticker, timeframe='4h', limit=100)
        #candles = candles[:-1]
        df = pd.DataFrame(candles, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
        df.set_index('datetime', inplace=True)

        df = df.sort_index()

        df = df[:-1]

        df['3ma'] = df['close'].rolling(window=3).mean()
        df['21ma'] = df['close'].rolling(window=21).mean()
        df['84ma'] = df['close'].rolling(window=84).mean()

        df['noise'] = 1 - abs(df['close'] - df['open']) / (df['high'] - df['low'])
        #df['noise'] = df['noise'].fillna(0)
        df['noise_ma'] = df['noise'].rolling(window=14).mean()
        #df['noise_ma'] = df['noise_ma'].fillna(0)
        df['vol-rate'] = (df['high'] - df['low']) / (df['high'].shift(1) - df['low'].shift(1))
        #df['vol-rate'] = df['vol-rate'].fillna(0)
        self.candles_8hr_ticker[ticker] = df

    def update_8hr_candle(self, ticker, open, high, low, close):
        new_row = {'open': open, 'high': high, 'low': low, 'close': close}

        if len(self.candles_8hr_ticker[ticker]) > 0:
            new_index = self.candles_8hr_ticker[ticker].index.max() + timedelta(hours=8)
        else:
            new_index = pd.Timestamp.now()

        self.candles_8hr_ticker[ticker].loc[new_index] = new_row
        # print(len(self.candles_8hr_ticker[ticker]))
        self.candles_8hr_ticker[ticker]['noise'] = 1 - abs(
            self.candles_8hr_ticker[ticker]['close'] - self.candles_8hr_ticker[ticker]['open']) / (
                                                               self.candles_8hr_ticker[ticker]['high'] -
                                                               self.candles_8hr_ticker[ticker]['low'])
        self.candles_8hr_ticker[ticker]['noise_ma'] = self.candles_8hr_ticker[ticker]['noise'].rolling(window=14).mean()

        self.candles_8hr_ticker[ticker]['vol-rate'] = (self.candles_8hr_ticker[ticker]['high'] -
                                                       self.candles_8hr_ticker[ticker]['low']) / (
                                                                  self.candles_8hr_ticker[ticker]['high'].shift(1) -
                                                                  self.candles_8hr_ticker[ticker]['low'].shift(1))

        if len(self.candles_8hr_ticker[ticker]) > 20:
            self.candles_8hr_ticker[ticker] = self.candles_8hr_ticker[ticker].iloc[-20:]

    def save_to_excel_if_needed(self):
        #if len(df) >= 20:
            # 현재 저장된 파일의 최대 순번을 확인
        file_number = 1
        while os.path.exists(f'output_{file_number}.xlsx'):
            file_number += 1

        # 새로운 파일명 생성
        file_name = f'output_{file_number}.xlsx'

        # 엑셀로 저장
        self.df_for_log.to_excel(file_name, index=False, engine='openpyxl')
        # print(f"Dataframe saved to {file_name}")

        # 데이터프레임 초기화
        self.df_for_log.drop(self.df_for_log.index, inplace=True)

    def toggle_resetcheck(self):
        if not self.reset_operating:
            self.reset_operating = True
            self.reset_check.setStyleSheet("background-color: darkblue; color: white;")
        else:
            self.reset_check.setStyleSheet("")
            self.reset_operating = False
            self.input_result.append("reset_operating is False")

    def stop_toggle_resetcheck(self):
        if self.reset_operating:
            return  # 이미 중지되어 있으면 중지하지 않음
        self.reset_operating = False
        self.input_result.append("reset_operating is False")

    def toggle_search(self):
        if not self.is_searching:
            self.searchButton.setStyleSheet("background-color: darkblue; color: white;")
            self.start_search_cp()
        else:
            self.searchButton.setStyleSheet("")
            self.stop_search_cp()

    def start_search_cp(self):
        if self.is_searching:
            return  # 이미 실행 중이면 시작하지 않음

        if self.search.text():
            try:
                self.input_result.append(f"{self.search.text()} 현재가: {self.close_8hr[self.search.text()]} 5평균: {self.ma[self.search.text()]}")
            except:
                self.input_result.append("심볼이 정확하지 않습니다.")

        self.is_searching = False

    def stop_search_cp(self):
        if self.is_searching:
            return  # 이미 실행 중이면 시작하지 않음
        self.is_searching = True
        self.input_result.clear()

    def handle_price(self, data):
        data_symbol = data['data'].get('s', '')
        if data['data'].get('k'):
            self.cp[data_symbol] = float(data['data']['k']['c']) if data['data']['k']['c'] else self.cp[data_symbol]
            #self.previous_n[data_symbol] = self.present_n[data_symbol]
            #self.present_n[data_symbol] = float(data['data']['k']['n'])
            #self.vol[data_symbol] = float(data['data']['k']['v'])
            self.ma[data_symbol] = self.average_last_five(self.recent_prices[data_symbol], float(data['data']['k']['c']))

            if self.checkbox_show.isChecked():
                self.input_log.append(f"{data_symbol} 현재가: {self.cp[data_symbol]} 5평균: {self.ma[data_symbol]}")
            else:
                self.input_log.clear()

            #if self.search.text()

            if str(data['data']['k']['x']) == 'True' and data_symbol in self.recent_prices:
                self.ohlc[data_symbol]['open'].append(float(data['data']['k']['o']))
                self.ohlc[data_symbol]['high'].append(float(data['data']['k']['h']))
                self.ohlc[data_symbol]['low'].append(float(data['data']['k']['l']))
                self.ohlc[data_symbol]['close'].append(float(data['data']['k']['o']))
                self.recent_prices[data_symbol].append(float(data['data']['k']['c']))

    def handle_position(self, data):

        if 'e' in data and data['e'] == 'ORDER_TRADE_UPDATE' and data['o']['X'] == 'PARTIALLY_FILLED':
            if float(data['o']['rp']) > 0:
                self.transfer_balance("fromfuture", float(data['o']['rp']) / 2)

        if 'e' in data and data['e'] == 'ORDER_TRADE_UPDATE' and data['o']['X'] == 'FILLED':
            symbol = data['o']['s']
            avg_price = data['o']['ap']
            amt = float(data['o']['q']) * (-1 if data['o']['S'] != 'BUY' else 1)
            current = datetime.now().time()

            if data['o']['c'] == "strategy_v2":

                #print(f"✅ [DEBUG] 데이터 추가됨: {symbol}, A:{self.position_A[symbol]}, B:{self.position_B[symbol]}")

                #await self.db_queue.put_nowait(
                #    (symbol, self.position_A[symbol], self.position_B[symbol]))  # ✅ Queue에 추가

                if self.positions[symbol] == 0 or self.positions[symbol] is None:
                    self.position_prices[symbol] = float(avg_price)
                    self.positions[symbol] = float(amt)
                    return

                elif self.positions[symbol] != 0:
                    new_position = self.positions[symbol] + amt
                    if new_position == 0:
                        self.positions[symbol] = new_position
                        self.position_prices[symbol] = 0

                    else:
                        new_avg_price = (abs(self.positions[symbol]) * self.position_prices[symbol] + float(avg_price) * abs(float(amt))) / abs(new_position)
                        self.positions[symbol] = new_position
                        self.position_prices[symbol] = new_avg_price

                    if float(data['o']['rp']) > 0:
                        self.transfer_balance("fromfuture", float(data['o']['rp']) / 2)

            if data['o']['c'] == "strategy_breakout":
                if current.hour in self.timezone_A:
                    if self.position_A.get(symbol, 0) == 0:  # ✅ 기존 값이 없으면 초기화
                        self.position_A[symbol] = float(amt)
                    else:
                        self.position_A[symbol] += float(amt)  # ✅ 중복 방지

                elif current.hour in self.timezone_B:
                    if self.position_B.get(symbol, 0) == 0:  # ✅ 기존 값이 없으면 초기화
                        self.position_B[symbol] = float(amt)
                    else:
                        self.position_B[symbol] += float(amt)  # ✅ 중복 방지

                self.db_buffer.put((symbol, self.position_A[symbol], self.position_B[symbol], current.strftime('%H:%M:%S')))

                if self.breakout_positions[symbol] == 0 or self.breakout_positions[symbol] is None:
                    self.breakout_position_prices[symbol] = float(avg_price)
                    self.breakout_positions[symbol] = float(amt)
                    return

                elif self.breakout_positions[symbol] != 0:
                    new_position = self.breakout_positions[symbol] + amt
                    if new_position == 0:
                        self.breakout_positions[symbol] = new_position
                        self.breakout_position_prices[symbol] = 0

                    else:
                        new_avg_price = (abs(self.breakout_positions[symbol]) * self.breakout_positions[symbol] + float(avg_price) * abs(float(amt))) / abs(new_position)
                        self.breakout_positions[symbol] = new_position
                        self.breakout_position_prices[symbol] = new_avg_price

                    if float(data['o']['rp']) > 0:
                        self.transfer_balance("fromfuture", float(data['o']['rp']) / 2)

            if data['o']['c'] == "strategy_ORB":
                if self.orb_positions[symbol] == 0 or self.orb_positions[symbol] is None:
                    self.orb_position_prices[symbol] = float(avg_price)
                    self.orb_positions[symbol] = float(amt)
                    return

                elif self.orb_positions[symbol] != 0:
                    new_position = self.orb_positions[symbol] + amt
                    if new_position == 0:
                        self.orb_positions[symbol] = new_position
                        self.orb_position_prices[symbol] = 0

                    else:
                        new_avg_price = (abs(self.orb_positions[symbol]) * self.orb_position_prices[symbol] + float(avg_price) * abs(float(amt))) / abs(new_position)
                        self.orb_positions[symbol] = new_position
                        self.orb_position_prices[symbol] = new_avg_price

                    if float(data['o']['rp']) > 0:
                        self.transfer_balance("fromfuture", float(data['o']['rp']) / 2)

    #진입조건
    #long: 1시, 9시, 17시 각 30분의 Open_range(=high - low) * k(0.7) + high 를 현재가가 상향돌파하고, 돌파시점부터 15분 뒤에 상향돌파를 유지하고 있으면 매수
    #short: 1시, 9시, 17시 각 30분의 low - Open_range(=high - low) * k(0.7) 를 현재가가 하향돌파하고, 돌파시점부터 15분 뒤에 하향돌파를 유지하고 있으면 매도

    #청산조건
    #익절: (long) 진입가격 + Open_range 상향돌파, (short) 진입가격 - open_range 하향돌파
    #가격손절: (long) open_low 하향돌파, (short) open_high 상향돌파
    #시간손절: 매일 1시, 9시, 17시 포지션 전체 종료
    def open_range_breakout(self):
        now = datetime.now()

        # 시간 범위 설정
        period_1_start = time(1, 31)  # 01:31
        period_1_end = time(9, 0)  # 09:00

        period_2_start = time(9, 31)  # 09:31
        period_2_end = time(17, 0)  # 17:00

        period_3_start = time(17, 31)  # 17:31
        period_3_end = time(1, 0)  # 01:00 (다음 날)

        if self.start_process:
            asyncio.run(self.orb_chart_load_v2())
            self.start_process = False

        target_times = [(1, 31), (9, 31), (17, 31)]  # (hour, minute)
        if (now.hour, now.minute) in target_times:
            if self.last_executed is not None and (now - self.last_executed).total_seconds() < 60:
                pass
            else:
                asyncio.run(self.orb_chart_load_v2())
                self.last_executed = now

            #elif self.last_executed is not None and (now - self.last_executed).total_seconds() >= 60:
            #    asyncio.run(self.orb_chart_load_v2())
            #    self.last_executed = now

        for ticker in self.converted_tickerlist:
            #print(self.cp[ticker], self.orb_short_target[ticker], self.orb_long_target[ticker])
            #self.orb_chart_load(ticker, now)

            if self.cp[ticker] is None or self.orb_short_target[ticker] is None or self.orb_long_target[ticker] is None:
                self.logger.info(f"{ticker} 데이터 적재 실패\n")
                continue

            if (period_1_start <= now.time() < period_1_end) or (period_2_start <= now.time() < period_2_end) or (now.time() >= period_3_start or now.time() < period_3_end):  # period_3은 하루를 넘어감
                if self.cp[ticker] >= float(self.orb_long_target[ticker]):
                    self.orb_signal_times[ticker] = datetime.now(), "long_sign", self.cp[ticker]

                if self.cp[ticker] <= float(self.orb_short_target[ticker]):
                    self.orb_signal_times[ticker] = datetime.now(), "short_sign", self.cp[ticker]

                if self.orb_signal_times[ticker][0] is not None and (datetime.now() - self.orb_signal_times[ticker][0]).total_seconds() > 900:
                    cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else self.api_call_to_get_balance['free']['USDT']
                    available_amt = 100
                    coin = ticker[:-4] + '/' + ticker[-4:]
                    if self.orb_signal_times[ticker][1] == "long_sign" and self.orb_signal_times[ticker][2] <= self.cp[ticker]:
                        self.logger.info(f"{ticker} ORB long_sign 주문발생(long open)\n")
                        try:
                            self.long_open(self.client, coin, available_amt, "strategy_ORB")

                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} ORB long open 실패\n")

                        self.orb_signal_times[ticker] = None, None, None

                    elif self.orb_signal_times[ticker][1] == "long_sign" and self.orb_signal_times[ticker][2] > self.cp[ticker]:
                        self.logger.info(f"{ticker} ORB long_sign, but pass\n")
                        self.orb_signal_times[ticker] = None, None, None


                    if self.orb_signal_times[ticker][1] == "short_sign" and self.orb_signal_times[ticker][2] >= self.cp[ticker]:
                        self.logger.info(f"{ticker} ORB short_sign 주문발생(long open)\n")
                        try:
                            self.short_open(self.client, coin, available_amt, "strategy_ORB")

                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} ORB short open 실패\n")

                        self.orb_signal_times[ticker] = None, None, None

                    elif self.orb_signal_times[ticker][1] == "short_sign" and self.orb_signal_times[ticker][2] < self.cp[ticker]:
                        self.logger.info(f"{ticker} ORB short_sign, but pass\n")
                        self.orb_signal_times[ticker] = None, None, None

                if self.orb_positions[ticker] is not None and float(self.orb_positions[ticker]) > 0 and float(self.orb_position_prices[ticker]) + float(self.open_range[ticker]) <= float(self.cp[ticker]):
                    self.logger.info(f"{ticker} ORB, long_close 발생.\n")
                    try:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.long_close(self.client, coin, self.orb_positions[ticker], "strategy_ORB")

                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} ORB long_close 실패\n")

                elif self.orb_positions[ticker] is not None and float(self.orb_positions[ticker]) > 0 and float(self.orb_short_target[ticker]) >= float(self.cp[ticker]):
                    self.logger.info(f"{ticker} ORB, long_close 손절발생.\n")
                    try:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.long_close(self.client, coin, self.orb_positions[ticker], "strategy_ORB")

                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} ORB long_close 실패\n")

                if self.orb_positions[ticker] is not None and float(self.orb_positions[ticker]) < 0 and float(self.orb_position_prices[ticker]) - float(self.open_range[ticker]) >= float(self.cp[ticker]):
                    self.logger.info(f"{ticker} ORB, short_close 발생.\n")
                    try:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.short_close(self.client, coin, self.orb_positions[ticker], "strategy_ORB")

                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} ORB short_close 실패\n")

                elif self.orb_positions[ticker] is not None and float(self.orb_positions[ticker]) < 0 and float(self.orb_long_target[ticker]) <= float(self.cp[ticker]):
                    self.logger.info(f"{ticker} ORB, short_close 손절발생.\n")
                    try:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.short_close(self.client, coin, self.orb_positions[ticker], "strategy_ORB")

                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} ORB short_close 실패\n")

                # 1시, 9시, 17시 강제 청산 조건
                current_hour = datetime.now().time()
                if current_hour.hour in [1, 9, 17] and current_hour.minute == 0 and self.orb_positions[ticker] != 0:
                    self.logger.info(f"{ticker} {current_hour}시 강제 청산 발생.\n")
                    try:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        if float(self.orb_positions[ticker]) > 0:
                            self.long_close(self.client, coin, self.orb_positions[ticker], "strategy_ORB")
                        else:
                            self.short_close(self.client, coin, self.orb_positions[ticker], "strategy_ORB")

                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} ORB 강제 청산 실패\n")

    async def orb_chart_load_v2(self):
        tasks = [self.get_30m_chart(symbol) for symbol in self.converted_tickerlist]
        await asyncio.gather(*tasks)

    #진입조건
    #1. (숏)1분봉 현재가 - 5평선 괴리률 +3% 발생, (롱)1분봉 현재가 - 5평선 괴리률 -3% 발생
    #2. 1번조건 발생한 시점 직후 캔들(T+1)에서 지난 시점, (숏)괴리시점의 가격 >= 현재가, (롱)괴리시점의 가격 <= 현재가
    #3. 8시간봉 기준, (숏) 음봉 or 양봉인 경우, (현재가 - 시가) >= (고가 - 현재가) (롱) 양봉 or 음봉인 경우, (시가 - 현재가) >= (현재가 - 저가)

    #피라미딩횟수: 3회

    #청산조건
    #1. 0.7% 이익
    #2. 1시, 9시, 17시 시점에 포지션 전체 강제종료
    #3. 8h_candle 기준, (숏) 고가,저가 평균 상향 돌파 (롱) 고가,저가 평균 하향 돌파

    def strategy_1(self, ticker):
        if self.ma[ticker] is not None and self.cp[ticker] >= self.ma[ticker] * 1.03 and float(
                self.pyramidings[ticker]) <= 0:
            self.signal_times[ticker] = datetime.now(), "over_long", self.cp[ticker]

        if self.ma[ticker] is not None and self.cp[ticker] <= self.ma[ticker] * 0.97 and float(
                self.pyramidings[ticker]) >= 0:
            self.signal_times[ticker] = datetime.now(), "over_short", self.cp[ticker]

        if self.signal_times[ticker][0] is not None:
            signal_time = self.signal_times[ticker][0]
            next_minute = signal_time + timedelta(minutes=1)
            next_minute = next_minute.replace(second=0)
            current_time = datetime.now()
            if current_time >= next_minute:
                cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                    self.api_call_to_get_balance['free']['USDT']
                available_amt = round(float(50) / float(self.cp[ticker]), 3)
                coin = ticker[:-4] + '/' + ticker[-4:]

                condition1 = self.signal_times[ticker][1] == "over_long"
                condition2 = self.ohlc[ticker]['high'][-1] >= self.cp[ticker]
                condition3 = self.pyramidings[ticker] >= -3
                condition4_1 = self.ohlc[ticker]['close'][-1] / self.ohlc[ticker]['high'][-1] <= (1-0.236)
                condition4_2 = self.ohlc[ticker]['close'][-1] / self.ohlc[ticker]['high'][-1] >= (1-0.382)

                condition5 = self.signal_times[ticker][1] == "over_short"
                condition6 = self.ohlc[ticker]['low'][-1] <= self.cp[ticker]
                condition7 = self.pyramidings[ticker] <= 3
                condition8_1 = self.ohlc[ticker]['close'][-1] / self.ohlc[ticker]['low'][-1] >= (1 + 0.236)
                condition8_2 = self.ohlc[ticker]['close'][-1] / self.ohlc[ticker]['low'][-1] <= (1 + 0.382)

                if condition1 and condition2 and condition3 and condition4_1 and condition4_2:
                    self.logger.info(f"{ticker} short_sign 주문발생(shot open)\n")
                    try:
                        self.short_open(self.client, coin, available_amt, "strategy_v2")
                        self.pyramidings[ticker] = self.pyramidings[ticker] - 1
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} short open 실패\n")
                    except:
                        pass

                    self.signal_times[ticker] = None, None, None

                elif condition5 and condition6 and condition7 and condition8_1 and condition8_2:
                    self.logger.info(f"{ticker} long_sign 주문발생(long open)\n")
                    try:
                        self.long_open(self.client, coin, available_amt, "strategy_v2")
                        self.pyramidings[ticker] = self.pyramidings[ticker] + 1
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} long open 실패\n")
                    except:
                        pass

                    self.signal_times[ticker] = None, None, None

                else:
                    self.logger.info(f"{ticker} pass")
                    self.logger.info(f"condition1: {condition1}, condition2: {condition2}, condition3: {condition3}, condition4: {condition4_1}")
                    self.logger.info(f"condition5: {condition5}, condition6: {condition6}, condition7: {condition7}, condition8: {condition8_1}\n")

                    self.signal_times[ticker] = None, None, None

        if self.positions[ticker] is not None and float(self.positions[ticker]) > 0:
            if float(self.position_prices[ticker]) * (1 + 0.007) <= float(self.cp[ticker]):
                self.logger.info(f"{ticker} 0.7% 수익발생, long_close 발생.\n")
                try:
                    coin = ticker[:-4] + '/' + ticker[-4:]
                    self.long_close(self.client, coin, self.positions[ticker], "strategy_v2")
                    self.pyramidings[ticker] = 0
                except (ValueError, KeyError, TypeError) as e:
                    self.logger.error(e)
                    self.logger.info(f"{ticker} long_close 실패\n")
                except:
                    pass

            if self.cp[ticker] < self.open_8hr[ticker] + (self.high_8hr[ticker] - self.open_8hr[ticker]) * 0.618 and self.loss_cut_time[ticker] is None:
                self.loss_cut_time[ticker] = datetime.now()


            if self.loss_cut_time[ticker] is not None:
                next_minute = self.loss_cut_time[ticker] + timedelta(minutes=5)
                next_minute = next_minute.replace(second=0)
                current_time = datetime.now()
                if current_time >= next_minute and self.close_8hr[ticker] < self.open_8hr[ticker] + (self.high_8hr[ticker] - self.open_8hr[ticker]) * 0.618:
                    self.logger.info(f"{ticker} loss-cut, long_close 발생.\n")
                    try:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.long_close(self.client, coin, self.positions[ticker], "strategy_v2")
                        self.pyramidings[ticker] = 0
                        self.loss_cut_time[ticker] = None
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} long_close 실패\n")
                    except:
                        pass

        if self.positions[ticker] is not None and float(self.positions[ticker]) < 0:
            if float(self.position_prices[ticker]) * (1 - 0.007) >= float(self.cp[ticker]):
                self.logger.info(f"{ticker} 0.7% 수익발생, short_close 발생.\n")
                try:
                    coin = ticker[:-4] + '/' + ticker[-4:]
                    self.short_close(self.client, coin, self.positions[ticker], "strategy_v2")
                    self.pyramidings[ticker] = 0
                except (ValueError, KeyError, TypeError) as e:
                    self.logger.error(e)
                    self.logger.info(f"{ticker} short_close 실패\n")
                except:
                    pass

            if self.cp[ticker] > self.open_8hr[ticker] - (self.open_8hr[ticker] - self.low_8hr[ticker]) * 0.618 and self.loss_cut_time[ticker] is None:
                self.loss_cut_time[ticker] = datetime.now()

            if self.loss_cut_time[ticker] is not None:
                next_minute = self.loss_cut_time[ticker] + timedelta(minutes=5)
                next_minute = next_minute.replace(second=0)
                current_time = datetime.now()
                if current_time >= next_minute and self.close_8hr[ticker] > self.open_8hr[ticker] - (self.open_8hr[ticker] - self.low_8hr[ticker]) * 0.618:
                    self.logger.info(f"{ticker} loss-cut, short_close 발생.\n")
                    try:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.short_close(self.client, coin, self.positions[ticker], "strategy_v2")
                        self.pyramidings[ticker] = 0
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} short_close 실패\n")
                    except:
                        pass
    # 역방향 변동성 돌파
    def strategy_2(self, ticker):
        if not self.candles_8hr_ticker[ticker].empty:
            if self.close_8hr[ticker] is not None and self.high_8hr[ticker] is not None and self.open_8hr[ticker] is not None and self.low_8hr[ticker] is not None:

                condition_red = self.candles_8hr_ticker[ticker]['close'].iloc[-1] > self.candles_8hr_ticker[ticker]['open'].iloc[-1]
                condition_blue = self.candles_8hr_ticker[ticker]['close'].iloc[-1] <= self.candles_8hr_ticker[ticker]['open'].iloc[-1]
                
                if condition_red:
                    condition_red_1 = self.close_8hr[ticker] >= self.open_8hr[ticker] + (self.candles_8hr_ticker[ticker]['open'].iloc[-1] - self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    condition_red_2 = self.close_8hr[ticker] <= self.open_8hr[ticker] - (self.candles_8hr_ticker[ticker]['open'].iloc[-1] - self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    condition3 = self.candles_8hr_ticker[ticker]['vol-rate'].iloc[-1] < 1.5
                    condition4 = self.breakout_positions[ticker] == 0
                    
                    if condition_red_1 and condition3 and condition4:
                        cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                            self.api_call_to_get_balance['free']['USDT']
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'long')
                        print(adj_amt)
                        available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        new_row = {
                            'Timestamp': current_time,
                            'Ticker': ticker,
                            'Current Price': self.cp[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])
                        self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                        try:
                            self.long_open(self.client, coin, available_amt, "strategy_breakout")
                            # self.pyramidings[ticker] = self.pyramidings[ticker] + 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} long open 실패\n")
                        except:
                            pass


                    if condition_red_2 and condition3 and condition4:
                        cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                            self.api_call_to_get_balance['free']['USDT']
                        # available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'short')
                        print(adj_amt)
                        available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        new_row = {
                            'Timestamp': current_time,
                            'Ticker': ticker,
                            'Current Price': self.cp[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])
                        self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                        # self.logger.info(f"{ticker} 변동성 돌파주문발생 list_from_low_vol(short open) >> 현재가: {self.close_8hr[ticker]}, 시가: {self.open_8hr[ticker]}, 전일고가: {self.candles_8hr_ticker[ticker]['high'].iloc[-1]}, 전일저가: {self.candles_8hr_ticker[ticker]['low'].iloc[-1]}, 노이즈: {self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]}\n")
                        try:
                            self.short_open(self.client, coin, available_amt, "strategy_breakout")
                            # self.pyramidings[ticker] = self.pyramidings[ticker] - 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} short open 실패\n")
                        except:
                            pass

                if condition_blue:
                    condition_blue_1 = self.close_8hr[ticker] >= self.open_8hr[ticker] + (self.candles_8hr_ticker[ticker]['high'].iloc[-1] - self.candles_8hr_ticker[ticker]['open'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    condition_blue_2 = self.close_8hr[ticker] <= self.open_8hr[ticker] - (self.candles_8hr_ticker[ticker]['high'].iloc[-1] - self.candles_8hr_ticker[ticker]['oepn'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    condition3 = self.candles_8hr_ticker[ticker]['vol-rate'].iloc[-1] < 1.5
                    condition4 = self.breakout_positions[ticker] == 0


                    if condition_blue_1 and condition3 and condition4:
                        cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                            self.api_call_to_get_balance['free']['USDT']
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'long')
                        print(adj_amt)
                        available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        new_row = {
                            'Timestamp': current_time,
                            'Ticker': ticker,
                            'Current Price': self.cp[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])
                        self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                        try:
                            self.long_open(self.client, coin, available_amt, "strategy_breakout")
                            # self.pyramidings[ticker] = self.pyramidings[ticker] + 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} long open 실패\n")
                        except:
                            pass


                    if condition_blue_2 and condition3 and condition4:
                        cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                            self.api_call_to_get_balance['free']['USDT']
                        # available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'short')
                        print(adj_amt)
                        available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        new_row = {
                            'Timestamp': current_time,
                            'Ticker': ticker,
                            'Current Price': self.cp[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])
                        self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                        # self.logger.info(f"{ticker} 변동성 돌파주문발생 list_from_low_vol(short open) >> 현재가: {self.close_8hr[ticker]}, 시가: {self.open_8hr[ticker]}, 전일고가: {self.candles_8hr_ticker[ticker]['high'].iloc[-1]}, 전일저가: {self.candles_8hr_ticker[ticker]['low'].iloc[-1]}, 노이즈: {self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]}\n")
                        try:
                            self.short_open(self.client, coin, available_amt, "strategy_breakout")
                            # self.pyramidings[ticker] = self.pyramidings[ticker] - 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} short open 실패\n")
                        except:
                            pass

                if self.breakout_positions[ticker] > 0:
                    if self.close_8hr[ticker] < self.open_8hr[ticker]:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.long_close(self.client, coin, self.breakout_positions[ticker], "strategy_breakout")

                if self.breakout_positions[ticker] < 0:
                    if self.close_8hr[ticker] > self.open_8hr[ticker]:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.short_close(self.client, coin, self.breakout_positions[ticker], "strategy_breakout")

                '''
                condition1 = self.close_8hr[ticker] >= self.open_8hr[ticker] + (self.candles_8hr_ticker[ticker]['high'].iloc[-1] - self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                condition2 = self.close_8hr[ticker] <= self.open_8hr[ticker] - (self.candles_8hr_ticker[ticker]['high'].iloc[-1] - self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                condition3 = self.candles_8hr_ticker[ticker]['vol-rate'].iloc[-1] < 1.5
                condition4 = self.breakout_positions[ticker] == 0

                if condition1 and condition3 and condition4:
                    cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                        self.api_call_to_get_balance['free']['USDT']
                    #available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                    if self.input_asset.text():
                        amt = str(self.input_asset.text())
                    else:
                        amt = 10
                    adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'long')
                    print(adj_amt)
                    available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                    coin = ticker[:-4] + '/' + ticker[-4:]
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    new_row = {
                        'Timestamp': current_time,
                        'Ticker': ticker,
                        'Current Price': self.cp[ticker],
                        'Open Price': self.open_8hr[ticker],
                        'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                        'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                        'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                    try:
                        self.long_open(self.client, coin, available_amt, "strategy_breakout")
                        # self.pyramidings[ticker] = self.pyramidings[ticker] + 1
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} long open 실패\n")
                    except:
                        pass

                if condition2 and condition3 and condition4:
                    cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                        self.api_call_to_get_balance['free']['USDT']
                    #available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                    if self.input_asset.text():
                        amt = str(self.input_asset.text())
                    else:
                        amt = 10
                    adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'short')
                    print(adj_amt)
                    available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                    coin = ticker[:-4] + '/' + ticker[-4:]
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    new_row = {
                        'Timestamp': current_time,
                        'Ticker': ticker,
                        'Current Price': self.cp[ticker],
                        'Open Price': self.open_8hr[ticker],
                        'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                        'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                        'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                    #self.logger.info(f"{ticker} 변동성 돌파주문발생 list_from_low_vol(short open) >> 현재가: {self.close_8hr[ticker]}, 시가: {self.open_8hr[ticker]}, 전일고가: {self.candles_8hr_ticker[ticker]['high'].iloc[-1]}, 전일저가: {self.candles_8hr_ticker[ticker]['low'].iloc[-1]}, 노이즈: {self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]}\n")
                    try:
                        self.short_open(self.client, coin, available_amt, "strategy_breakout")
                        # self.pyramidings[ticker] = self.pyramidings[ticker] - 1
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} short open 실패\n")
                    except:
                        pass
                '''


    # 정방향 변동성 돌파
    def strategy_3(self, ticker):
        current = datetime.now().time()
        if not self.candles_8hr_ticker[ticker].empty:
            if self.close_8hr[ticker] is not None and self.high_8hr[ticker] is not None and self.open_8hr[ticker] is not None and self.low_8hr[ticker] is not None:

                condition_red = self.candles_8hr_ticker[ticker]['close'].iloc[-1] > self.candles_8hr_ticker[ticker]['open'].iloc[-1] + (self.candles_8hr_ticker[ticker]['high'].iloc[-2] - self.candles_8hr_ticker[ticker]['low'].iloc[-2]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-2]
                condition_blue = self.candles_8hr_ticker[ticker]['close'].iloc[-1] <= self.candles_8hr_ticker[ticker]['open'].iloc[-1] - (self.candles_8hr_ticker[ticker]['high'].iloc[-2] - self.candles_8hr_ticker[ticker]['low'].iloc[-2]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-2]

                if condition_red:
                    condition_red_1 = self.close_8hr[ticker] >= self.open_8hr[ticker] + (
                                self.candles_8hr_ticker[ticker]['open'].iloc[-1] -
                                self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * \
                                      self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    condition_red_2 = self.close_8hr[ticker] <= self.open_8hr[ticker] - (
                                self.candles_8hr_ticker[ticker]['open'].iloc[-1] -
                                self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * \
                                      self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    #condition3 = self.candles_8hr_ticker[ticker]['vol-rate'].iloc[-1] < 1.5
                    condition4 = self.breakout_positions[ticker] == 0
                    condition5 = self.order_opened[ticker] is False
                    condition6 = False
                    if current in self.timezone_A:
                        condition6 = self.position_A[ticker] == 0
                    else:
                        condition6 = self.position_B[ticker] == 0

                    if condition_red_1 and condition4 and condition5 and condition6:
                        #cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else self.api_call_to_get_balance['free']['USDT']
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        #adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'long')
                        available_amt = round(float(amt) / float(self.close_8hr[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        price = self.open_8hr[ticker] + (float(self.candles_8hr_ticker[ticker]['open'].iloc[-1]) - float(self.candles_8hr_ticker[ticker]['low'].iloc[-1])) * float(self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1])



                        new_row = {
                            'Timestamp': current,
                            'Ticker': ticker,
                            'Current Price': self.close_8hr[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])

                        try:
                            self.short_open(self.client,coin=coin,price=price,amt=available_amt,clientOrderId="strategy_breakout")
                            self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                            self.order_opened[ticker] = True
                            # self.pyramidings[ticker] = self.pyramidings[ticker] + 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} long open 실패\n")
                        except:
                            pass

                    '''
                    if condition_red_2 and condition4:
                        cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                            self.api_call_to_get_balance['free']['USDT']
                        # available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'short')
                        print(adj_amt)
                        available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        new_row = {
                            'Timestamp': current_time,
                            'Ticker': ticker,
                            'Current Price': self.cp[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])
                        self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                        # self.logger.info(f"{ticker} 변동성 돌파주문발생 list_from_low_vol(short open) >> 현재가: {self.close_8hr[ticker]}, 시가: {self.open_8hr[ticker]}, 전일고가: {self.candles_8hr_ticker[ticker]['high'].iloc[-1]}, 전일저가: {self.candles_8hr_ticker[ticker]['low'].iloc[-1]}, 노이즈: {self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]}\n")
                        try:
                            self.short_open(self.client, coin, available_amt, "strategy_breakout")
                            # self.pyramidings[ticker] = self.pyramidings[ticker] - 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} short open 실패\n")
                        except:
                            pass
                    '''

                elif condition_blue:
                    condition_blue_1 = self.close_8hr[ticker] >= self.open_8hr[ticker] + (
                                self.candles_8hr_ticker[ticker]['high'].iloc[-1] -
                                self.candles_8hr_ticker[ticker]['open'].iloc[-1]) * \
                                       self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    condition_blue_2 = self.close_8hr[ticker] <= self.open_8hr[ticker] - (
                                self.candles_8hr_ticker[ticker]['high'].iloc[-1] -
                                self.candles_8hr_ticker[ticker]['open'].iloc[-1]) * \
                                       self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    #condition3 = self.candles_8hr_ticker[ticker]['vol-rate'].iloc[-1] < 1.5
                    condition4 = self.breakout_positions[ticker] == 0
                    condition5 = self.order_opened[ticker] is False
                    condition6 = False
                    if current in self.timezone_A:
                        condition6 = self.position_A[ticker] == 0
                    else:
                        condition6 = self.position_B[ticker] == 0

                    '''
                    if condition_blue_1 and condition4:
                        cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                            self.api_call_to_get_balance['free']['USDT']
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'long')
                        print(adj_amt)
                        available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        new_row = {
                            'Timestamp': current_time,
                            'Ticker': ticker,
                            'Current Price': self.cp[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])
                        self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                        try:
                            self.long_open(self.client, coin, available_amt, "strategy_breakout")
                            # self.pyramidings[ticker] = self.pyramidings[ticker] + 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} long open 실패\n")
                        except:
                            pass
                    '''

                    if condition_blue_2 and condition4 and condition5 and condition6:
                        #cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else self.api_call_to_get_balance['free']['USDT']
                        # available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                        if self.input_asset.text():
                            amt = str(self.input_asset.text())
                        else:
                            amt = 10
                        #adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'short')

                        available_amt = round(float(amt) / float(self.close_8hr[ticker]), 3)
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        price = self.open_8hr[ticker] - (float(self.candles_8hr_ticker[ticker]['high'].iloc[-1]) - float(self.candles_8hr_ticker[ticker]['open'].iloc[-1])) * float(self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1])

                        new_row = {
                            'Timestamp': current,
                            'Ticker': ticker,
                            'Current Price': self.close_8hr[ticker],
                            'Open Price': self.open_8hr[ticker],
                            'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                            'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                            'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                        }
                        new_row_df = pd.DataFrame([new_row])

                        try:
                            self.long_open(self.client, coin=coin, price=price, amt=available_amt, clientOrderId="strategy_breakout")

                            self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                            self.order_opened[ticker] = True
                            # self.pyramidings[ticker] = self.pyramidings[ticker] - 1
                        except (ValueError, KeyError, TypeError) as e:
                            self.logger.error(e)
                            self.logger.info(f"{ticker} short open 실패\n")
                        except:
                            pass

                '''
                if self.breakout_positions[ticker] > 0:
                    if self.close_8hr[ticker] < self.open_8hr[ticker]:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.long_close(self.client, coin, self.breakout_positions[ticker], "strategy_breakout")

                if self.breakout_positions[ticker] < 0:
                    if self.close_8hr[ticker] > self.open_8hr[ticker]:
                        coin = ticker[:-4] + '/' + ticker[-4:]
                        self.short_close(self.client, coin, self.breakout_positions[ticker], "strategy_breakout")
                '''

                '''
                condition0 = (datetime.now() - self.candles_8hr_ticker[ticker].index[-1]) <= timedelta(hours=8)
                condition1 = self.close_8hr[ticker] >= self.open_8hr[ticker] + (self.candles_8hr_ticker[ticker]['high'].iloc[-1] - self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                condition2 = self.close_8hr[ticker] <= self.open_8hr[ticker] - (self.candles_8hr_ticker[ticker]['high'].iloc[-1] - self.candles_8hr_ticker[ticker]['low'].iloc[-1]) * self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                #condition3 = self.candles_8hr_ticker[ticker]['vol-rate'].iloc[-1] < 1.5
                condition4 = self.breakout_positions[ticker] == 0


                if condition1 and condition4:
                    cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                        self.api_call_to_get_balance['free']['USDT']
                    #available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                    if self.input_asset.text():
                        amt = str(self.input_asset.text())
                    else:
                        amt = 10
                    adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'long')
                    print(adj_amt)
                    available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                    coin = ticker[:-4] + '/' + ticker[-4:]
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    new_row = {
                        'Timestamp': current_time,
                        'Ticker': ticker,
                        'Current Price': self.cp[ticker],
                        'Open Price': self.open_8hr[ticker],
                        'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                        'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                        'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                    #self.logger.info(f"{ticker} 변동성 돌파주문발생 list_from_high_vol(long open) >> 현재가: {self.close_8hr[ticker]}, 시가: {self.open_8hr[ticker]}, 전일고가: {self.candles_8hr_ticker[ticker]['high'].iloc[-1]}, 전일저가: {self.candles_8hr_ticker[ticker]['low'].iloc[-1]}, 노이즈: {self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]}\n")
                    try:
                        self.long_open(self.client, coin, available_amt, "strategy_breakout")
                        # self.pyramidings[ticker] = self.pyramidings[ticker] + 1
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} long open 실패\n")
                    except:
                        pass

                if condition2 and condition4:
                    cash_total = self._cached_balance['free']['USDT'] if self._cached_balance else \
                        self.api_call_to_get_balance['free']['USDT']
                    #available_amt = round(float(cash_total) / float(self.cp[ticker]), 3)
                    if self.input_asset.text():
                        amt = str(self.input_asset.text())
                    else:
                        amt = 10
                    adj_amt = self.cal_asset_for_trade(ticker, float(amt), 'short')
                    print(adj_amt)
                    available_amt = round(adj_amt / float(self.cp[ticker]), 3)
                    coin = ticker[:-4] + '/' + ticker[-4:]
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    new_row = {
                        'Timestamp': current_time,
                        'Ticker': ticker,
                        'Current Price': self.cp[ticker],
                        'Open Price': self.open_8hr[ticker],
                        'Prev High': self.candles_8hr_ticker[ticker]['high'].iloc[-1],
                        'Prev Low': self.candles_8hr_ticker[ticker]['low'].iloc[-1],
                        'Noise': self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.df_for_log = pd.concat([self.df_for_log, new_row_df], ignore_index=True)
                    #self.logger.info(f"{ticker} 변동성 돌파주문발생 list_from_high_vol(short open) >> 현재가: {self.close_8hr[ticker]}, 시가: {self.open_8hr[ticker]}, 전일고가: {self.candles_8hr_ticker[ticker]['high'].iloc[-1]}, 전일저가: {self.candles_8hr_ticker[ticker]['low'].iloc[-1]}, 노이즈: {self.candles_8hr_ticker[ticker]['noise_ma'].iloc[-1]}\n")
                    try:
                        self.short_open(self.client, coin, available_amt, "strategy_breakout")
                        # self.pyramidings[ticker] = self.pyramidings[ticker] - 1
                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.error(e)
                        self.logger.info(f"{ticker} short open 실패\n")
                    except:
                        pass
                '''

    def strategy_test(self,ticker):
        if ticker in self.vol_rate_from_low and not self.candles_8hr_ticker[ticker].empty:
            print(ticker)
            print(self.candles_8hr_ticker[ticker])

    def get_unrealized_PnL(self, ticker):
        #if all(self.cp[ticker], self.breakout_position_prices[ticker], self.breakout_positions[ticker]) is not None:
        if self.close_8hr[ticker] is not None and self.breakout_position_prices[ticker] is not None and self.breakout_positions[ticker] is not None:
            self.breakout_pnl[ticker] = (self.close_8hr[ticker] - float(self.breakout_position_prices[ticker])) * float(self.breakout_positions[ticker])

    def close_half_position(self):

        positions = self.api_call_to_get_balance()['info']['positions']

        for pos in positions:
            if float(pos['positionAmt']) != 0:
                position_amt = float(pos['positionAmt']) / 2
                symbol = pos['symbol']
                side = 'sell' if position_amt > 0 else 'buy'
                binance.create_order(self.client,
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=abs(position_amt),  # 포지션 전체 수량 종료
                    params={"reduceOnly": True}  # 기존 포지션만 줄임
                )

    def cancel_all_orders(self):
        url = 'https://fapi.binance.com/fapi/v1/allOpenOrders'
        API_KEY = config.API_KEY
        API_SECRET = config.API_SECRET

        open_orders = self.get_open_orders()

        if not open_orders:
            print("취소할 열린 주문이 없습니다.")
            return

        for order in open_orders:
            symbol = order['symbol']
            order_id = order['orderId']
            self.cancel_order(symbol, order_id)

    def cancel_order(self, symbol, order_id):
        """주문 취소"""
        url = 'https://fapi.binance.com/fapi/v1/order'
        API_KEY = config.API_KEY
        API_SECRET = config.API_SECRET

        timestamp = int(time.time() * 1000)
        query_string = f'symbol={symbol}&orderId={order_id}&timestamp={timestamp}'
        signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

        headers = {'X-MBX-APIKEY': API_KEY}
        response = requests.delete(f'{url}?{query_string}&signature={signature}', headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"주문 취소 오류: {response.status_code} - {response.text}")
            return None

    def get_open_orders(self):
        url = 'https://fapi.binance.com/fapi/v1/openOrders'
        API_KEY = config.API_KEY
        API_SECRET = config.API_SECRET

        # 타임스탬프 생성
        timestamp = int(time.time() * 1000)

        # 쿼리 스트링 구성 (심볼 생략 시 모든 심볼의 열린 주문 조회)
        query_string = f'timestamp={timestamp}'
        signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

        # 헤더 설정
        headers = {
            'X-MBX-APIKEY': API_KEY
        }

        try:
            response = requests.get(f'{url}?{query_string}&signature={signature}', headers=headers, timeout=10)
            response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Binance API 요청 실패: {e}")
            return None

    def close_all_position_timezone_A(self):
        for symbol, position_amt in self.position_A.items():  # ✅ 딕셔너리에서 symbol과 positionAmt 가져오기
            if float(position_amt) != 0:  # 포지션이 0이 아니면 종료
                side = 'sell' if position_amt > 0 else 'buy'
                ticker = symbol[:-4] + "/" + symbol[-4:]
                binance.create_order(self.client,
                                     symbol=symbol,
                                     type='market',
                                     # price=float(self.open_8hr[symbol]),
                                     side=side,
                                     amount=abs(position_amt),  # 포지션 전체 수량 종료
                                     params={"reduceOnly": False}  # 기존 포지션만 줄임
                                     )

    def close_all_position_timezone_B(self):
        for symbol, position_amt in self.position_B.items():  # ✅ 딕셔너리에서 symbol과 positionAmt 가져오기
            if float(position_amt) != 0:  # 포지션이 0이 아니면 종료
                side = 'sell' if position_amt > 0 else 'buy'
                ticker = symbol[:-4] + "/" + symbol[-4:]
                binance.create_order(self.client,
                                     symbol=symbol,
                                     type='market',
                                     # price=float(self.open_8hr[symbol]),
                                     side=side,
                                     amount=abs(position_amt),  # 포지션 전체 수량 종료
                                     params={"reduceOnly": False}  # 기존 포지션만 줄임
                                     )


    def close_all_position(self):

        positions = self.api_call_to_get_balance()['info']['positions']

        for pos in positions:
            if float(pos['positionAmt']) != 0:
                position_amt = float(pos['positionAmt'])
                symbol = pos['symbol']
                side = 'sell' if position_amt > 0 else 'buy'
                binance.create_order(self.client,
                    symbol=symbol,
                    type='market',
                    #price=float(self.open_8hr[symbol]),
                    side=side,
                    amount=abs(position_amt),  # 포지션 전체 수량 종료
                    params={"reduceOnly": True}  # 기존 포지션만 줄임
                )

    def change_order_to_market(self):
        url = 'https://fapi.binance.com/fapi/v1/allOpenOrders'
        API_KEY = config.API_KEY
        API_SECRET = config.API_SECRET

        open_orders = self.get_open_orders()

        if not open_orders:
            #print("취소할 열린 주문이 없습니다.")
            return

        current_time = datetime.now()
        #current_time = datetime.fromtimestamp(int(datetime.utcnow()))
        for order in open_orders:
            try:
                # 주문 정보 추출
                symbol = order['symbol']
                order_id = order['orderId']
                order_time = datetime.fromtimestamp(order['time'] / 1000)  # 밀리초를 초로 변환 후 datetime으로 변환
                #order_time_unix = int(order_time.timestamp())
                order_side = order['side']
                order_amt = float(order['origQty'])  # 수량을 float으로 변환

                # 디버깅용 출력
                #print(symbol, order_id, order_time, order_side, order_amt)
                #print(type(symbol), type(order_id), type(order_time), type(order_side), type(order_amt))

                # 2분 초과 여부 확인
                if current_time - order_time > timedelta(minutes=2):
                    print(f"주문 {order_id}가 2분을 초과했습니다. 시장가로 전환합니다.")

                    # 심볼 변환: BTCUSDT -> BTC/USDT
                    coin = symbol[:-4] + '/' + symbol[-4:]

                    # 기존 주문 취소
                    self.cancel_order(symbol, order_id)

                    # 시장가 주문으로 전환
                    if order_side != "BUY":
                        print("short_open")
                        self.short_open(client=self.client, coin=coin, price=None, amt=order_amt,
                                        clientOrderId='strategy_breakout')
                    else:
                        print("long_open")
                        self.long_open(client=self.client, coin=coin, price=None, amt=order_amt,
                                       clientOrderId='strategy_breakout')

            except Exception as e:
                print(f"주문 처리 중 오류 발생: {e}")

    def contiue_all_position(self):

        url = 'https://fapi.binance.com/fapi/v2/account'

        API_KEY = config.API_KEY
        API_SECRET = config.API_SECRET

        # 타임스탬프 생성
        timestamp = int(time.time() * 1000)

        # 서명 생성
        query_string = f'timestamp={timestamp}'
        signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

        # 헤더 설정
        headers = {
            'X-MBX-APIKEY': API_KEY
        }

        # 요청 보내기
        response = requests.get(f'{url}?{query_string}&signature={signature}', headers=headers)
        positions = response.json()['positions']

        for pos in positions:
            if float(pos['positionAmt']) != 0:
                position_amt = float(pos['positionAmt'])
                average_price = float(pos['entryPrice'])
                symbol = pos['symbol']
                ticker = symbol[:-4] + symbol[-4:]
                if symbol in self.converted_tickerlist:
                    self.breakout_positions[symbol] = position_amt
                    self.breakout_position_prices[symbol] = average_price
                else:
                    self.breakout_positions[ticker] = 0

    def load_positions_from_db(self, db_path="trading_positions.db", table_name="positions"):
        """
        SQLite에서 포지션 데이터를 불러와서 self.position_A, self.position_B를 업데이트하는 함수
        """
        try:

            if not os.path.exists(db_path):
                print(f"⚠️ {db_path} 파일이 존재하지 않습니다. DB 로드를 건너뜁니다.")
                return

            # 1️⃣ SQLite 데이터베이스 연결
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 2️⃣ 테이블에서 데이터 가져오기
            cursor.execute(f"SELECT symbol, position_A, position_B FROM {table_name}")
            rows = cursor.fetchall()  # [(symbol, position_A, position_B), ...]

            # 3️⃣ 기존 포지션 초기화
            self.position_A = {symbol: 0 for symbol in self.converted_tickerlist}
            self.position_B = {symbol: 0 for symbol in self.converted_tickerlist}

            # 4️⃣ 가져온 데이터로 포지션 업데이트
            for symbol, position_A, position_B in rows:
                self.position_A[symbol] = float(position_A)
                self.position_B[symbol] = float(position_B)

            # 5️⃣ 연결 종료
            conn.close()
            print(f"✅ DB에서 포지션 데이터를 불러와 업데이트 완료")

        except Exception as e:
            print(f"❌ DB 로드 중 오류 발생: {e}")

    def save_positions_to_db(self, data_list, db_path="trading_positions.db", table_name="positions"):
        """
        Queue에서 받은 데이터 리스트를 한꺼번에 DB에 저장
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                symbol TEXT PRIMARY KEY,
                position_A REAL,
                position_B REAL,
                timestamp TEXT
            )
            """)
            cleaned_data = [(symbol, position_A or 0.0, position_B or 0.0, timestamp) for
                            symbol, position_A, position_B, timestamp in data_list]
            #timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

            # 4️⃣ 데이터 리스트 한 번에 저장
            cursor.executemany(f"""
            INSERT INTO {table_name} (symbol, position_A, position_B, timestamp)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                position_A = excluded.position_A,
                position_B = excluded.position_B,
                timestamp = excluded.timestamp
            """, cleaned_data)

            conn.commit()
            conn.close()
            print(f"✅ [DEBUG] {len(data_list)}개 포지션이 DB에 저장되었습니다.")

        except Exception as e:
            print(f"❌ [DEBUG] DB 저장 중 오류 발생: {e}")

    def db_saver(self):
        """
        비동기적으로 Queue에 저장된 포지션을 일정 간격(예: 1초)마다 DB에 저장
        """

        if not self.db_buffer.empty():
            data_list = []
            while not self.db_buffer.empty():
                data = self.db_buffer.get()
                data_list.append(data)

            self.save_positions_to_db(data_list)  # ✅ 한 번에 여러 데이터 저장

    def strategy_operator(self):
        #amt = str(self.input_asset.text())
        #print(amt)
        for ticker in self.converted_tickerlist:
            #self.get_unrealized_PnL(ticker)
            try:
                #if self.reset_operating:
                #    self.strategy_1(ticker)

                #if ticker in self.vol_rate_from_low and self.reset_operating:
                #    self.strategy_2(ticker)

                if self.reset_operating:
                    self.strategy_3(ticker)

            except (ValueError, KeyError, TypeError) as e:
                self.logger.error(e)
            except:
                pass
        current = datetime.now().time()
        if self.reset_operating:
            self.change_order_to_market()
            self.db_saver()

        '''
        if self.input_asset.text():
           if sum(self.breakout_pnl.values()) >= float(str(self.input_asset.text())) / 2 and self.profit_realized <= 1:
                self.close_half_position()
                self.profit_realized = self.profit_realized + 1

        if self.input_asset.text():
           if sum(self.breakout_pnl.values()) >= float(str(self.input_asset.text())) and self.profit_realized <= 1:
                self.close_half_position()
                self.profit_realized = self.profit_realized + 1

        if self.input_asset.text():
           if sum(self.breakout_pnl.values()) <= -1 * float(str(self.input_asset.text())) / 2 and self.loss_realized <= 1:
                self.close_half_position()
                self.loss_realized = self.loss_realized + 1

        if self.input_asset.text():
           if sum(self.breakout_pnl.values()) <= -1 * float(str(self.input_asset.text())) and self.loss_realized <= 1:
                self.close_half_position()
                self.loss_realized  = self.loss_realized + 1
        '''

        if current.hour in [1, 5, 9, 13, 17, 21] and current.minute == 0 and self.reset_operating:
            print(f"✅ [DEBUG] Resetting at {current.hour}:{current.minute}:{current.second}")
            self.reset_operating = False
            self.profit_realized = 0
            self.loss_realized = 0
            self.cancel_all_orders()

            if current.hour in self.timezone_A:
                print("✅ [DEBUG] Closing positions for Timezone A")
                self.close_all_position_timezone_A()
            else:
                print("✅ [DEBUG] Closing positions for Timezone B")
                self.close_all_position_timezone_B()

            #self.close_all_position()

        if current.hour in [1, 5, 9, 13, 17, 21] and current.minute == 2 and not self.reset_operating:
            tickers = list(self.binance_futures.fetch_tickers().keys())
            self.tickerlist = [tickers[i][:-5] for i in range(len(tickers)) if tickers[i][-4:] == 'USDT']
            self.converted_tickerlist = [ticker.replace('/', '') for ticker in self.tickerlist if ticker.replace('/', '') != 'USDCUSDT']
            self.candles_8hr_ticker = {symbol: None for symbol in self.converted_tickerlist}
            for ticker in self.converted_tickerlist:
                if current.hour in self.timezone_A:
                    self.position_A[ticker] = 0
                else:
                    self.position_B[ticker] = 0
                self.db_buffer.put(
                    (ticker, self.position_A[ticker], self.position_B[ticker], current.strftime('%H:%M:%S')))
                self.breakout_positions[ticker] = 0
                self.order_opened[ticker] = False
                #self.positions[ticker] = 0
                try:
                    self.get_8hr_candle(ticker)
                except:
                    pass


            #self.rank_last_vol_rate()

            self.reset_operating = True
            #self.save_positions_to_db()
            self.logger.info(f"{current} 데이터 초기화 및 전략 재시작")

        if current.hour == 1 and current.minute == 2:
            self.stop_main()
            self.start_main()


    def initialize_loop(self):
        """클래스 내부에서 asyncio 이벤트 루프를 초기화"""
        self.loop = asyncio.get_event_loop()

    def toggle_main(self):
        if not self.is_running:
            self.run_strategy.setStyleSheet("background-color: darkblue; color: white;")
            self.start_main()
        else:
            self.run_strategy.setStyleSheet("")
            self.stop_main()

    def start_main(self):
        if self.is_running:
            return  # 이미 실행 중이면 시작하지 않음
        self.is_running = True
        self.input_log.append("전략 감지 시작")
        self.strategy_timer3 = QTimer(self)
        self.strategy_timer3.setInterval(10000)  # 10초마다
        self.strategy_timer3.timeout.connect(self.strategy_operator)
        #self.strategy_timer3.timeout.connect(self.test_print_not_asyncio)
        #self.strategy_timer3.timeout.connect(self.run_async_task)
        #self.strategy_timer3.timeout.connect(self.open_range_breakout)
        self.strategy_timer3.start()

    def stop_main(self):
        if not self.is_running:
            return  # 이미 중지되어 있으면 중지하지 않음
        self.is_running = False
        self.input_log.append("전략 감지 중지")
        # 타이머를 중지합니다.
        self.strategy_timer3.stop()

    def get_server_time(self):
        BASE_URL = "https://fapi.binance.com"
        url = f"{BASE_URL}/fapi/v1/time"
        response = requests.get(url)
        return response.json()['serverTime']

    # 요청에 서명을 추가하는 함수
    def get_max_leverage(self, symbol):
        BASE_URL = "https://fapi.binance.com"
        API_KEY = config.API_KEY
        API_SECRET = config.API_SECRET

        headers = {
            'X-MBX-APIKEY': API_KEY
        }

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

        # 각 종목에 대해 최대 레버리지를 찾음
        for bracket in data:
            if bracket['symbol'] == symbol:
                return max([int(br['initialLeverage']) for br in bracket['brackets']])
        return None

    # 사용자가 입력한 레버리지와 비교하여 최소값을 설정
    def set_leverage(self, symbol, user_leverage):

        max_leverage = self.get_max_leverage(symbol)
        #print(max_leverage)
        BASE_URL = "https://fapi.binance.com"
        API_KEY = config.API_KEY
        API_SECRET = config.API_SECRET

        headers = {
            'X-MBX-APIKEY': API_KEY
        }

        if max_leverage is None:
            print(f"{symbol}의 최대 레버리지를 가져올 수 없습니다.")
            return

        leverage_to_set = min(max_leverage, user_leverage)
        # 바이낸스 서버 시간 가져오기
        timestamp = self.get_server_time()
        params = {
            "symbol": symbol,
            "leverage": leverage_to_set,
            "timestamp": timestamp
        }

        # signed_payload = sign_request(payload)
        query_string = '&'.join([f"{key}={params[key]}" for key in params])
        signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        params['signature'] = signature
        set_leverage_url = f"{BASE_URL}/fapi/v1/leverage"
        response = requests.post(set_leverage_url, headers=headers, params=params)
        #print(response)

    def long_open(self, client, coin, price=None, amt=None, clientOrderId=None):
        params = {}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId

        self.set_leverage(coin.replace('/', ''), 20)
        if price is None:
            binance.create_market_order(client, coin, 'buy', amt, params=params)
        else:
            binance.create_order(client, symbol=coin, type='limit', side='buy', price=price, amount=amt, params=params)
        #binance.create_market_order(client, coin, 'buy', amt, params=params)
        #self.update_balance_cache()

    def short_open(self, client, coin, price=None, amt=None, clientOrderId=None):
        params = {}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId
        #binance.set_leverage(client, 20, coin)
        self.set_leverage(coin.replace('/', ''), 20)
        if price is None:
            binance.create_market_order(client, coin, 'sell', amt, params=params)
        else:
            binance.create_order(client, symbol=coin, type='limit', side='sell', price=price, amount=amt, params=params)
        #binance.create_market_order(client, coin, 'sell', amt, params=params)
        #self.update_balance_cache()

    def long_close(self, client, coin, positions, clientOrderId=None):
        params = {'reduceOnly': True}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId
        binance.create_market_order(client, coin, 'sell', float(positions), params=params)
        self.update_balance_cache()

    def short_close(self, client, coin, positions, clientOrderId=None):
        params = {'reduceOnly': True}
        if clientOrderId is not None:
            params['clientOrderId'] = clientOrderId
        binance.create_market_order(client, coin, 'buy', -float(positions), params=params)
        self.update_balance_cache()

    def setup_logger(self):
        self.logger = logging.getLogger("websocket_log")
        self.logger.setLevel(logging.INFO)

        # 기존 핸들러 제거
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        handler = TimedRotatingFileHandler(
            filename='websocket_log.log',
            when='D',
            interval=1,
            backupCount=0,
            encoding='utf-8'
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def api_load(self):
        return ccxt.binance(config={
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            },
        })

    async def get_30m_chart(self, ticker):
        try:
            candles = ccxt.binanceus.fetch_ohlcv(self.client, symbol=ticker, timeframe='30m', limit=2)
            candle = candles[0]
            self.orb_candle_30m[ticker][0] = float(candle[1])
            self.orb_candle_30m[ticker][1] = float(candle[2])
            self.orb_candle_30m[ticker][2] = float(candle[3])
            self.orb_candle_30m[ticker][3] = float(candle[4])

            self.open_range[ticker] = self.orb_candle_30m[ticker][1] - self.orb_candle_30m[ticker][2]
            self.orb_long_target[ticker] = self.orb_candle_30m[ticker][1] + self.open_range[ticker] * 0.7
            self.orb_short_target[ticker] = self.orb_candle_30m[ticker][2] - self.open_range[ticker] * 0.7

            #return ticker
        except Exception as e:
            self.logger.error(f"{ticker} 8시간봉 데이터를 가져오는 중 오류 발생: {str(e)}")
            return

    def update_balance_cache(self):
        # Fetch the latest balance data and update the cache
        self._cached_balance = self.api_call_to_get_balance()

    def api_call_to_get_balance(self):
        return ccxt.binanceus.fetch_balance(self.api_load(), params={"type": "future", 'recvWindow': 10000000})

    def cal_asset_for_trade(self, ticker, amt, side):
        # 3평, 21평, 84평

        condition1, condition2, condition3 = 0, 0, 0
        condition4, condition5, condition6 = 0, 0, 0
        if self.candles_8hr_ticker[ticker]['3ma'].iloc[-1] is not None:
            condition1 = 1 if self.close_8hr[ticker] > self.candles_8hr_ticker[ticker]['3ma'].iloc[-1] else 0
            condition4 = 1 if self.close_8hr[ticker] <= self.candles_8hr_ticker[ticker]['3ma'].iloc[-1] else 0
        if self.candles_8hr_ticker[ticker]['21ma'].iloc[-1] is not None:
            condition2 = 1 if self.close_8hr[ticker] > self.candles_8hr_ticker[ticker]['21ma'].iloc[-1] else 0
            condition5 = 1 if self.close_8hr[ticker] <= self.candles_8hr_ticker[ticker]['21ma'].iloc[-1] else 0
        if self.candles_8hr_ticker[ticker]['84ma'].iloc[-1] is not None:
            condition3 = 1 if self.close_8hr[ticker] > self.candles_8hr_ticker[ticker]['84ma'].iloc[-1] else 0
            condition6 = 1 if self.close_8hr[ticker] <= self.candles_8hr_ticker[ticker]['84ma'].iloc[-1] else 0

        long_ma_score = (condition1 + condition2 + condition3) / 3
        short_ma_score = (condition4 + condition5 + condition6) / 3

        amt_by_ma_score = 0

        if side != 'long':
            amt_by_ma_score = amt * short_ma_score
        else:
            amt_by_ma_score = amt * long_ma_score

        condition_last_vol = (self.candles_8hr_ticker[ticker]['high'].iloc[-1] - self.candles_8hr_ticker[ticker]['low'].iloc[-1]) / self.candles_8hr_ticker[ticker]['close'].iloc[-1]
        limit_to_input = 0.03 / condition_last_vol
        amt_result = amt * limit_to_input

        return float(amt_result)

    def transfer_balance(self, side, amt):
        api_key = config.API_KEY
        api_secret = config.API_SECRET

        client = Client(api_key, api_secret)

        # 사용 예시: 현물에서 선물로 USDT 이체
        if side == "fromspot":
            client.make_universal_transfer(type="MAIN_UMFUTURE", asset="USDT", amount=amt)

        # 사용 예시: 선물에서 현물로 USDT 이체
        if side == "fromfuture":
            client.make_universal_transfer(type="UMFUTURE_MAIN", asset="USDT", amount=amt)

    def list_num(self, ticker):
        list_symbol = self._cached_balance['info']['positions']
        tickers = ticker[:-4] + ticker[-4:]

        for i in range(len(list_symbol)):
            if list_symbol[i]['symbol'] == tickers:
                return i

    def average_last_five(self, lst, num):
        # if not isinstance(lst, list):
        #    raise TypeError("The first argument must be a list.")
        # if not isinstance(num, (int, float)):
        #    raise TypeError("The second argument must be an int or a float.")

        if len(lst) == self.period:
            # lst.pop(len(lst) - 1)
            last_five_values = list(lst)[-4:]
            average = (sum(last_five_values) + num) / (len(last_five_values) + 1)
            return average
        else:
            return None

    def export_variables_to_excel(self):
        self.input_result.append(f"변수 상태가 파일로 저장되었습니다.")
        try:
            # 변수 데이터를 수집
            data = {
                "Variable Name": [
                    "cp", "ma", "positions", "pyramidings", "candles_8hr_ticker",
                    "df_for_log", "open_8hr", "high_8hr", "low_8hr", "close_8hr"
                ],
                "Values": [
                    str(self.cp),  # 현재가
                    str(self.ma),  # 이동평균
                    str(self.positions),  # 현재 포지션
                    str(self.pyramidings),  # 피라미딩 상태
                    str(self.candles_8hr_ticker),  # 돌파 전략 포지션
                    str(self.df_for_log),  # ORB 전략 포지션
                    str(self.open_8hr),  # 8시간 봉 시가
                    str(self.high_8hr),  # 8시간 봉 고가
                    str(self.low_8hr),  # 8시간 봉 저가
                    str(self.close_8hr)  # 8시간 봉 종가
                ]
            }

            # DataFrame 생성
            df = pd.DataFrame(data)

            # 파일 저장
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"exported_variables_{now}.xlsx"
            df.to_excel(file_name, index=False, engine='openpyxl')

            # 성공 메시지
            self.input_result.append(f"변수 상태가 {file_name} 파일로 저장되었습니다.")
        except Exception as e:
            self.input_result.append(f"엑셀 저장 중 오류 발생: {str(e)}")

    def binance_24hr_increase(self):
        url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Sort the data by 24-hour price increase percentage
            sorted_data = sorted([x for x in data if x['symbol'].endswith('USDT')],
                                 key=lambda x: float(x['priceChangePercent']),
                                 reverse=True)
            return sorted_data
        else:
            print("Error:", response.status_code)
            return []

    def get_top_coins_by_growth(self):
        coinmarketcap_api_key = '79433af7-9e71-4882-89dd-c7292ed546b5'
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': coinmarketcap_api_key,
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()['data']
            return {coin['symbol']: coin['quote']['USD']['percent_change_24h'] for coin in data}
        else:
            raise Exception("CoinMarketCap API error", response.status_code)

    def get_top_10_cryptos(self, api_key):
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': api_key,
        }

        top_cryptos = []
        start = 1
        limit = 20
        while len(top_cryptos) < 10:
            parameters = {
                'start': str(start),
                'limit': str(limit),
                'convert': 'USD'
            }

            response = requests.get(url, headers=headers, params=parameters)

            if response.status_code == 200:
                data = response.json()
                for crypto in data['data']:
                    if crypto['symbol'] not in ['USDT', 'USDC']:
                        top_cryptos.append(crypto['symbol'] + '/USDT')

                    if len(top_cryptos) == 10:
                        break
            else:
                return "Failed to retrieve data"

            start += limit

        return top_cryptos

    def get_total_market_cap(self):
        url = "https://api.coingecko.com/api/v3/global"
        try:
            response = requests.get(url)
            data = response.json()

            self.total_market_cap_change = data['data']['market_cap_change_percentage_24h_usd']
            # print(self.total_market_cap_change)
            # return data['data']['market_cap_change_percentage_24h_usd']
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

    async def send_chat(self, text):
        chat_token = "1890445272:AAFwXuubrD4hUNxv16kbkUPII6IQCpfdRP4"
        chat = telegram.Bot(token=chat_token)
        await chat.sendMessage(chat_id='404493922', text=text)

    def execute_main_dialog(self):
        """MainDialog 실행 함수, 비동기 루프를 클래스 내부에서 처리"""
        try:
            self.show()

        except Exception as e:
            # 비동기적으로 텔레그램으로 오류 메시지 전송
            asyncio.create_task(self.send_chat(str(e)))
            QApplication.quit()


if __name__ == '__main__':

    QApplication.setStyle("fusion")
    suppress_qt_warnings()
    app = QApplication(sys.argv)

    main_dialog = MainDialog()
    main_dialog.initialize_loop()

    try:
        main_dialog.execute_main_dialog()
        sys.exit(app.exec_())

    except requests.exceptions.ConnectionError:  # Replace with the specific exception if necessary
        # Wait for 10 seconds before retrying
        # asyncio.run(send_chat())
        #time.sleep(10)
        # execute_main_dialog()
        pass


    except Exception as e:

        # 예외 처리 및 메시지 전송

        asyncio.create_task(main_dialog.send_chat(str(e)))

        sys.exit(1)


    #execute_main_dialog()
    # main_dialog = MainDialog()
    # main_dialog.show()
    # sys.exit(app.exec_())