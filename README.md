
# 코인트레이딩 전략

📄 [변동성돌파 Counter-Trend 전략 개요](https://github.com/khw12369/Coin-Trader/blob/main/README.md#1.변동성Reversal_전략)

📄 [볼린져밴드 Counter-Trend 전략 백테스팅](https://github.com/khw12369/Coin-Trader/blob/main/backtest_BB(180%2C2).ipynb)

📄 [볼린져밴드 Counter-Trend 전략 개요](https://github.com/khw12369/Coin-Trader/blob/main/BB_Counter-Trend.py)

📄 [마켓메이킹: Spread Ask-Bid with Options]()

# 1.변동성돌파 Count-Trend_전략

## 개요
이 전략은 **4시간 봉 데이터를 기반으로 변동성 돌파 전략**을 수행하는 트레이딩 알고리즘입니다.  
이전 봉의 변동성을 고려하여 특정 가격 돌파 시 롱(Long) 또는 숏(Short) 포지션을 진입합니다.

## 코드 확인
이 전략의 구현 코드는 아래 파일에서 확인할 수 있습니다.

📄 [CB_reversal_v10.py](https://github.com/khw12369/Coin-Trader/blob/main/CB_reversal_v10.py)

---
## 입력 데이터
- `candles_8hr_ticker[ticker]`: 4시간 봉의 캔들 데이터 (`open`, `high`, `low`, `close`, `noise_ma` 등)
- `close_8hr[ticker]`: 현재 4시간 봉의 종가
- `open_8hr[ticker]`: 현재 4시간 봉의 시가
- `high_8hr[ticker]`: 현재 4시간 봉의 최고가
- `low_8hr[ticker]`: 현재 4시간 봉의 최저가
- `noise_ma`: 변동성 조정 계수 (이전 봉의 변동성을 고려한 값)
---
##  트레이딩 유니버스
-  바이낸스 선물 상장 티커 전체
---
## 트레이딩 조건
- **매도 (숏) 조건 (`condition_red`)**  
  - 종가가 시가 + (이전 봉의 고가 - 저가) * `noise_ma` 보다 클 경우
- **매수 (롱) 조건 (`condition_blue`)**  
  - 종가가 시가 - (이전 봉의 고가 - 저가) * `noise_ma` 보다 작을 경우

---

## 진입 조건
### 숏 포지션 (`condition_red_1`)
- 현재 8시간 봉의 종가가 **시가 + (이전 봉의 시가 - 저가) * `noise_ma`** 이상
- 기존 포지션 없음 (`breakout_positions == 0`)
- 기존 주문이 없음 (`order_opened == False`)
- 시간대에 따라 `position_A` 또는 `position_B`이 **0이어야 함** (중복 진입 방지)

### 롱 포지션 (`condition_blue_2`)
- 현재 8시간 봉의 종가가 **시가 - (이전 봉의 고가 - 시가) * `noise_ma`** 이하
- 기존 포지션 없음 (`breakout_positions == 0`)
- 기존 주문이 없음 (`order_opened == False`)
- 시간대에 따라 `position_A` 또는 `position_B`이 **0이어야 함** (중복 진입 방지)

---

## 진입 시 주문 실행
- `short_open()`을 호출하여 숏 포지션 진입
- `long_open()`을 호출하여 롱 포지션 진입
- 주문이 체결되면 `order_opened[ticker] = True`로 설정하여 **중복 주문 방지**
- 거래 로그 (`df_for_log`)에 트레이딩 데이터 저장

---

## 포지션 정리 조건 (현재 주석 처리됨)
- **숏 포지션 (`breakout_positions > 0`)**  
  - 종가가 시가보다 낮아지면 `long_close()` 실행
- **롱 포지션 (`breakout_positions < 0`)**  
  - 종가가 시가보다 높아지면 `short_close()` 실행

---

