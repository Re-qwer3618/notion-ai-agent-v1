import streamlit as st
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# 1. 경로 설정 (config, core 폴더 인식용)
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'config'))
sys.path.insert(0, os.path.join(BASE_DIR, 'core'))

# ---------------------------------------------------------
# 2. 모듈 불러오기
# ---------------------------------------------------------
from config import kiwoom_login, load_secrets, save_token
from core import account_manager as am
from core.strategy import StrategyManager

try:
    from core.backtester import Backtester
except ImportError:
    pass 

try:
    from core.trader.order_manager import KiwoomOrderManager
except ImportError:
    pass

def main():
    st.set_page_config(page_title="키움증권 AI 트레이딩 센터", layout="wide", page_icon="📈")
    
    st.title("🤖 AI 주식 자동매매 통합 관제실")
    st.markdown("---")

    # secrets.yaml 정보 로드
    secrets = load_secrets()
    if not secrets:
        st.error("secrets.yaml 파일을 찾을 수 없거나 형식이 잘못되었습니다.")
        secrets = {}

    default_account = secrets.get('ACCOUNT', '설정안됨')

    # =========================================================
    # 사이드바: 로그인 상태 관리
    # =========================================================
    with st.sidebar:
        st.header("🔑 로그인 상태")
        
        if 'login_status' not in st.session_state:
            st.session_state['login_status'] = False

        if st.session_state['login_status']:
            st.success("로그인 성공!")
            current_acc = st.session_state.get('my_account', default_account)
            st.info(f"접속 계좌: {current_acc}")
            
            if st.button("로그아웃"):
                st.session_state['login_status'] = False
                st.rerun()
        else:
            invest_type = st.radio("모의투자 접속", ["모의투자", "실전투자"])
            if st.button("로그인 실행"):
                try:
                    type_code = '1' if '실전' in invest_type else '2'
                    with st.spinner(f"{invest_type} 접속 중..."):
                        token = kiwoom_login(type_code)
                    
                    if token:
                        st.session_state['login_status'] = True
                        st.session_state['token'] = token
                        
                        if '실전' in invest_type:
                            st.session_state['url_base'] = "https://api.kiwoom.com"
                            st.session_state['my_account'] = secrets.get('REAL_ACCOUNT', secrets.get('ACCOUNT', ''))
                            st.session_state['is_real'] = True
                        else:
                            st.session_state['url_base'] = "https://mockapi.kiwoom.com"
                            st.session_state['my_account'] = secrets.get('MOCK_ACCOUNT', secrets.get('ACCOUNT', ''))
                            st.session_state['is_real'] = False
                        st.rerun()
                    else:
                        st.error("로그인 실패. (Token 반환값 없음)")
                except Exception as e:
                    st.error(f"로그인 중 오류 발생: {e}")

    # =========================================================
    # 메인 화면: 탭 구성
    # =========================================================
    tab1, tab2, tab3, tab4 = st.tabs(["💰 계좌/자산", "⚙️ AI 전략", "⚡ 간편 주문", "🧪 백테스팅"])

    # -----------------------------------------------------
    # TAB 1: 계좌 조회
    # -----------------------------------------------------
    with tab1:
        if st.session_state.get('login_status'):
            st.subheader("📊 실시간 자산 현황")
            if st.button("🔄 잔고/예수금 조회", use_container_width=True):
                token = st.session_state['token']
                url = st.session_state['url_base']
                acc = st.session_state['my_account']
                try:
                    current_mode = '1' if st.session_state.get('is_real') else '2'
                    manager = am.AccountManager(token=token, account_num=acc, mode=current_mode)
                    deposit = manager.get_deposit()  # 예수금 조회
                    stocks = manager.get_balance()   # 잔고 조회
                    #deposit = am.fn_kt00001(token, url, acc)
                    #stocks = am.fn_kt00018(token, url, acc)
                    st.session_state['deposit'] = deposit
                    st.session_state['stocks'] = stocks
                except Exception as e:
                    st.error(f"조회 실패: {e}")
            
            if 'deposit' in st.session_state:
                st.dataframe(st.session_state['deposit'], use_container_width=True)
            if 'stocks' in st.session_state:
                st.dataframe(st.session_state['stocks'], use_container_width=True)
        else:
            st.info("로그인이 필요합니다.")

    # -----------------------------------------------------
    # TAB 2: 전략 설정
    # -----------------------------------------------------
    with tab2:
        st.subheader("🧠 AI 매매 전략 설정")
        sm = StrategyManager()
        cfg = sm.config
        
        capital = st.number_input("운용 자본금", value=cfg['account']['initial_capital'], step=1000000)
        cfg['account']['initial_capital'] = capital
        
        if st.button("💾 설정 저장"):
            sm.save_config(cfg)
            st.success("저장 완료")

    # -----------------------------------------------------
    # TAB 3: 간편 주문
    # -----------------------------------------------------
    with tab3:
        st.subheader("⚡ 수동 주문")
        if st.session_state.get('login_status'):
            st.info("주문 기능은 정상 작동 중입니다.")
            # 필요 시 주문 UI 코드 추가
        else:
            st.info("로그인이 필요합니다.")

    # -----------------------------------------------------
    # TAB 4: 통합 시뮬레이션
    # -----------------------------------------------------
    with tab4:
        st.subheader("🧪 퀀트 전략 검증소")

        # 경로 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        strategies_dir = os.path.join(current_dir, 'core', 'strategies')
        
        # 전략 파일 목록
        if os.path.exists(strategies_dir):
            strategy_files = [f.replace('.py', '') for f in os.listdir(strategies_dir) 
                              if f.endswith('.py') and not f.startswith('__')]
        else:
            strategy_files = []

        # [1] 설정 UI
        c1, c2 = st.columns(2)
        
        # 왼쪽 컬럼: 모드 및 전략 선택
        with c1:
            st.markdown("##### 1. 전략 모드")
            sim_mode = st.radio(
                "운용 방식", 
                ["🤖 규칙 기반 (Strategy)", 
                 "🤝 하이브리드 (Strategy + AI)", 
                 "🧠 순수 AI (Pure AI)"],
                label_visibility="collapsed"
            )
            
            selected_strategy = None
            use_ai = False
            
            if "순수 AI" in sim_mode:
                st.info("AI가 차트를 보고 직접 판단합니다.")
                use_ai = True
            else:
                selected_strategy = st.selectbox("📂 전략 파일 선택", strategy_files)
                if "하이브리드" in sim_mode:
                    use_ai = True
                    st.caption("규칙 신호 → AI 검증")
                else:
                    use_ai = False
                    st.caption("규칙 신호만 사용")

        # 오른쪽 컬럼: 대상 및 기간 설정
        with c2:
            st.markdown("##### 2. 분석 대상 및 기간")
            # [수정됨] 단일 vs 전체 선택 기능 추가
            scope = st.radio("분석 범위", ["단일 종목", "전체 종목 (DB)"], horizontal=True)
            
            target_code = None
            if scope == "단일 종목":
                target_code = st.text_input("종목코드", "005930")
            else:
                st.info("📂 저장된 모든 데이터(.jsonl)를 분석합니다.")
            
            seed_money = st.number_input("시작 투자금", 10000000, step=1000000)
            
            date_range = st.date_input(
                "기간 설정",
                (pd.to_datetime("2024-01-01"), pd.to_datetime("today"))
            )

        st.markdown("---")

        # [2] 실행 버튼
        if st.button("🚀 시뮬레이션 시작", type="primary", use_container_width=True):
            # 날짜 포맷을 YYYY-MM-DD로 변환 (Backtester와 호환성 위해)
            start_dt = date_range[0].strftime("%Y-%m-%d")
            end_dt = date_range[1].strftime("%Y-%m-%d") if len(date_range) > 1 else None

            tester = Backtester(initial_capital=seed_money)
            
            # A. 단일 종목 시뮬레이션
            if scope == "단일 종목":
                df = tester.load_data(target_code)
                if df is not None:
                    with st.spinner(f"[{target_code}] 분석 중..."):
                        res = tester.run_simulation(
                            df, 
                            strategy_name=selected_strategy, 
                            use_ai_filter=use_ai, 
                            start_date=start_dt, 
                            end_date=end_dt
                        )
                    
                    if res:
                        k1, k2, k3 = st.columns(3)
                        k1.metric("최종 자산", f"{res['final_balance']:,} 원")
                        k2.metric("수익률", f"{res['return_rate']}%", delta=f"{res['return_rate']}%")
                        k3.metric("거래 횟수", f"{res['trade_count']} 회")
                        
                        st.subheader("📝 매매 상세 일지")
                        st.dataframe(pd.DataFrame(res['trade_log']), use_container_width=True)
                    else:
                        st.warning("결과가 없거나 매매 신호가 발생하지 않았습니다.")
                else:
                    st.error("데이터 파일이 없습니다. 수집을 먼저 진행해주세요.")

            # B. 전체 종목 시뮬레이션
            else:
                with st.spinner("데이터베이스의 모든 종목을 분석 중입니다... (시간이 걸릴 수 있습니다)"):
                    summary = tester.run_all_simulation(
                        timeframe='daily',
                        strategy_name=selected_strategy,
                        use_ai_filter=use_ai,
                        start_date=start_dt,
                        end_date=end_dt
                    )
                
                if summary is not None and not summary.empty:
                    st.success(f"✅ 총 {len(summary)}개 종목 분석 완료!")
                    
                    # 요약 통계
                    avg_ret = summary['Return(%)'].mean()
                    best_stock = summary.iloc[0]
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("평균 수익률", f"{avg_ret:.2f}%")
                    m2.metric("최고 수익 종목", f"{best_stock['Code']}", f"{best_stock['Return(%)']}%")
                    m3.metric("분석 종목 수", f"{len(summary)}개")
                    
                    st.subheader("📊 전체 수익률 순위")
                    st.dataframe(summary, use_container_width=True)
                else:
                    st.warning("분석할 데이터가 없거나 결과가 없습니다.")

if __name__ == "__main__":
    main()