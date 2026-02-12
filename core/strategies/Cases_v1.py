import pandas as pd 

def calculate(df, i):
    # 1. 데이터 부족하면 관망
    if i < 20: return 0, ""

    # 지표 직접 계산
    if 'SMA5' not in df.columns:
        df['SMA5'] = df['Close'].rolling(window=5).mean()
        df['SMA20'] = df['Close'].rolling(window=20).mean()

    # 데이터 가져오기
    today_sma5 = df['SMA5'].iloc[i]
    today_sma20 = df['SMA20'].iloc[i]
    prev_sma5 = df['SMA5'].iloc[i-1]
    prev_sma20 = df['SMA20'].iloc[i-1]
    
    # [디버깅용 로그] 매일매일 수치를 출력해봄 (너무 많으면 나중에 주석 처리)
    # print(f"날짜:{df.iloc[i]['Date']} | 5일선:{int(today_sma5)} | 20일선:{int(today_sma20)}")

    signal = 0
    reason = ""

    # 골든크로스
    if today_sma5 > today_sma20 and prev_sma5 <= prev_sma20:
        signal = 1
        reason = "골든크로스 (5>20)"
        print(f"🎉 [Cases_v1] 매수 신호 발견! ({df.iloc[i]['Date']})") # <--- 이게 뜨는지 확인!

    # 데드크로스
    elif today_sma5 < today_sma20 and prev_sma5 >= prev_sma20:
        signal = -1
        reason = "데드크로스 (5<20)"
        print(f"💧 [Cases_v1] 매도 신호 발견! ({df.iloc[i]['Date']})") # <--- 이게 뜨는지 확인!

    return signal, reason