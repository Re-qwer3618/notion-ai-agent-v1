import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import mplfinance as mpf
import streamlit as st

# =========================================================
# [설정] UI 및 파라미터 정의
# =========================================================
def strategy_ui():
    st.sidebar.markdown("### 🧱 Case 3: 지지선 반등 (MA Support)")
    st.sidebar.info("주요 이평선까지 눌렸을 때 지지를 받고 양봉이 뜨는 순간을 노립니다.")
    
    with st.expander("⚙️ 전략 파라미터", expanded=True):
        ma_period = st.selectbox("지지 이평선 선택", [20, 60, 120], index=0)
        tolerance = st.slider("지지선 근접 오차 (%)", 1.0, 5.0, 2.0, help="이평선과 얼마나 가까워야 지지로 인정할까요?")

    st.sidebar.markdown("---")
    tp = st.sidebar.number_input("목표 수익률(%)", value=15.0)
    sl = st.sidebar.number_input("손절 제한(%)", value=-5.0)

    return {"ma_period": ma_period, "tolerance": tolerance, "target_profit": tp, "stop_loss": sl}

# =========================================================
# [Part 1] 데이터 준비 및 지표 계산
# =========================================================
def prepare_data(df, config=None):
    """
    데이터에 기술적 지표와 신호를 계산하여 추가합니다.
    config가 없으면 기본값을 사용합니다.
    """
    if df is None or df.empty: return df

    # 기본 설정값 (외부에서 config가 안 넘어올 경우 대비)
    if config is None:
        config = {"ma_period": 20, "tolerance": 2.0}

    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)

    # 등락률 계산
    df['Day_Chg'] = df['Close'].pct_change() * 100
    
    # --- 로직: Case 3 ---
    ma_pd = config.get('ma_period', 20)
    ma_col = f'MA_{ma_pd}'
    tolerance = config.get('tolerance', 2.0) / 100.0
    
    # 이평선 계산
    df[ma_col] = df['Close'].rolling(ma_pd).mean()
    
    # 1. 지지선 근접 (저가가 이평선 근처까지 내려왔는가?)
    #    분모가 0이 되는 것을 방지하기 위해 epsilon 추가 혹은 처리
    if df[ma_col].iloc[-1] != 0: 
        dist_to_ma = abs(df['Low'] - df[ma_col]) / df[ma_col]
        near_support = dist_to_ma <= tolerance
    else:
        near_support = False
    
    # 2. 양봉 발생 (지지 확인: 종가가 시가보다 높음)
    is_bullish = df['Close'] > df['Open']
    
    # 3. 추세 필터 (종가가 이평선 위에 있거나 살짝 걸쳐야 함, 너무 깊게 빠지면 안됨)
    above_support = df['Close'] > (df[ma_col] * 0.98)
    
    # 최종 매수 신호 (이 신호는 당일 장 마감 기준임)
    df['Signal_Candidate'] = near_support & is_bullish & above_support
    df['Reason_Msg'] = np.where(df['Signal_Candidate'], f"Case3(MA{ma_pd}) 지지", "")
    
    return df

# =========================================================
# [Part 2] 외부 Backtester 연동용 함수 (추가됨)
# =========================================================
def calculate(df, i):
    """
    Backtester에서 매일 호출하는 함수.
    i 시점(오늘)에 매수해야 하는지 여부를 반환합니다.
    현실적인 백테스트를 위해 '어제(i-1)' 신호가 떴다면 '오늘(i)' 매수(1)를 반환합니다.
    """
    # 1. 데이터가 충분한지 확인
    if i < 20: return 0, "" # MA 계산 등을 위해 최소 기간 필요
    if 'Signal_Candidate' not in df.columns:
        # 데이터가 준비 안 되어 있으면 기본값으로 계산 (비효율적이지만 안전장치)
        prepare_data(df)

    # 2. [중요] 타임머신 방지 로직
    # 오늘(i) 매수를 하려면, 어제(i-1) 장 마감 후에 신호가 확정되어야 함.
    # 따라서 i-1일의 Signal_Candidate를 확인합니다.
    yesterday = i - 1
    
    if df.iloc[yesterday]['Signal_Candidate']:
        return 1, df.iloc[yesterday]['Reason_Msg'] # 1: 매수 신호
    
    return 0, "" # 신호 없음

# =========================================================
# [Part 3] 자체 시뮬레이션 함수 (수정됨)
# =========================================================
def execute_trade(df, config):
    # 기본 자금 설정
    initial_capital = config['account'].get('initial_capital', 10000000)
    fee_rate = config['account'].get('fee_rate', 0.00015)
    
    # TP/SL 설정
    tp_rate = config.get('target_profit', 15.0) / 100.0
    sl_rate = config.get('stop_loss', -5.0) / 100.0
    
    balance = initial_capital
    shares = 0
    avg_price = 0
    logs = []
    
    # 데이터 준비
    df = prepare_data(df, config)
    
    start_idx = max(config['ma_period'] + 1, 60)
    if len(df) < start_idx: return initial_capital, logs

    # 반복문 시작
    for i in range(start_idx, len(df)):
        curr_row = df.iloc[i]   # 오늘 데이터
        prev_row = df.iloc[i-1] # 어제 데이터
        
        # 1. 매도 (Sell) - 보유 중일 때만 검사
        if shares > 0:
            tp_price = avg_price * (1 + tp_rate) # 익절가
            sl_price = avg_price * (1 + sl_rate) # 손절가
            
            sell_price = 0
            reason = ""
            
            # 고가가 익절가보다 높으면 익절 체결
            if curr_row['High'] >= tp_price: 
                sell_price = max(curr_row['Open'], tp_price) # 갭상승 고려
                reason = "TP(익절)"
            # 저가가 손절가보다 낮으면 손절 체결
            elif curr_row['Low'] <= sl_price: 
                sell_price = min(curr_row['Open'], sl_price) # 갭하락 고려
                reason = "SL(손절)"
            
            # 매도 실행
            if sell_price > 0:
                revenue = shares * sell_price * (1 - fee_rate) # 수수료 차감
                profit = revenue - (shares * avg_price)
                profit_rate = ((sell_price - avg_price) / avg_price) * 100
                
                logs.append({
                    "Date": curr_row['Date'].strftime('%Y-%m-%d'), 
                    "Type": "Sell", 
                    "Price": int(sell_price), 
                    "Shares": shares, 
                    "Profit": int(profit),
                    "Profit_Rate": round(profit_rate, 2),
                    "Reason": reason, 
                    "Day_Chg(%)": round(curr_row['Day_Chg'], 2)
                })
                
                balance += revenue
                shares = 0
                avg_price = 0
                continue # 매도한 날에는 다시 매수하지 않음 (선택사항)
                
        # 2. 매수 (Buy)
        # [수정됨] 어제(prev_row) 신호가 떴다면, 오늘(curr_row) 시가에 매수
        if shares == 0 and prev_row['Signal_Candidate']:
            buy_price = curr_row['Open']
            buy_qty = int((balance * 0.99) / buy_price) # 예수금의 99%만 사용
            
            if buy_qty > 0:
                shares = buy_qty
                avg_price = buy_price
                fee = (buy_price * buy_qty) * fee_rate
                balance -= (buy_price * buy_qty) + fee
                
                logs.append({
                    "Date": curr_row['Date'].strftime('%Y-%m-%d'), 
                    "Type": "Buy", 
                    "Price": int(buy_price), 
                    "Shares": shares, 
                    "Profit": 0, 
                    "Profit_Rate": 0, 
                    "Reason": prev_row['Reason_Msg'], 
                    "Day_Chg(%)": round(curr_row['Day_Chg'], 2)
                })

    # 마지막 보유분 평가
    final_value = balance + (shares * df.iloc[-1]['Close'])
    return final_value, logs

# =========================================================
# [Part 4] 차트 생성 (기존 유지)
# =========================================================
def create_chart_image(df, logs, save_dir, code, config=None):
    if len(df) == 0: return
    
    # 시각화용 데이터 복사 및 인덱스 설정
    plot_df = df.copy()
    plot_df.set_index('Date', inplace=True)
    
    save_path = os.path.join(save_dir, f"{code}_chart.png")
    
    # 매매 포인트 표시 (Buy: ▲, Sell: ▼)
    # mpf.make_addplot을 사용하여 차트에 마커 추가 가능
    
    try: 
        # 간단한 캔들 차트
        mpf.plot(
            plot_df, 
            type='candle', 
            volume=True, 
            title=f"Case 3 (Support MA): {code}", 
            style='yahoo', 
            savefig=save_path, 
            figsize=(12,6)
        )
    except Exception as e:
        print(f"Chart generation failed: {e}")