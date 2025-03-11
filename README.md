# 변동성 돌파 전략 (CB_reversal_v10.py)

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

## 결론
이 전략은 변동성이 큰 시장에서 효과적인 **돌파 매매 전략**으로 활용될 수 있습니다.  
이전 봉의 변동성을 반영하여 특정 가격을 돌파하면 포지션을 취하고, 주문이 체결되면 **중복 주문을 방지**하도록 설계되었습니다.
