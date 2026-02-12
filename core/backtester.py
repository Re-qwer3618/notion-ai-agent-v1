import sys
import os
import importlib
import pandas as pd
import time # 진행 상황 표시를 위해 추가

# -----------------------------------------------------------
# [경로 설정] 프로젝트 루트(Stock_Data_V1) 강제 등록
# -----------------------------------------------------------
current_file_path = os.path.abspath(__file__)
root_path = os.path.dirname(os.path.dirname(current_file_path)) # core -> Project_Root
if root_path not in sys.path:
    sys.path.append(root_path)

# AI 전략 가져오기 (파일이 없어도 에러 안 나게 처리)
try:
    from core.ai_strategy import AIStrategy
except ImportError:
    AIStrategy = None

class Backtester:
    def __init__(self, initial_capital=10000000, fee_rate=0.00015, tax_rate=0.0020):
        self.initial_capital = initial_capital
        self.fee = fee_rate
        self.tax = tax_rate
        self.trade_log = [] 
        self.balance_history = []

    def load_data(self, code, timeframe='daily'):
        """특정 종목의 데이터를 로드합니다."""
        folder_name = "02_daily" if timeframe == 'daily' else "03_minute"
        file_path = os.path.join(root_path, "database", folder_name, f"{code}.jsonl")
        
        if not os.path.exists(file_path): return None
        try:
            df = pd.read_json(file_path, lines=True)
            return df.sort_values('Date').reset_index(drop=True)
        except: return None

    # ------------------------------------------------------------------
    # [기존 기능] 단일 종목 시뮬레이션
    # ------------------------------------------------------------------
    def run_simulation(self, df, strategy_name=None, use_ai_filter=False, start_date=None, end_date=None, silent=False):
        """
        단일 종목에 대해 백테스트를 수행합니다.
        silent=True일 경우, 상세 로그 출력을 끕니다 (전체 백테스팅용).
        """
        if df is None or df.empty: return None

        # [1] 전략 모듈 로딩
        strategy_module = None
        if strategy_name and strategy_name != "None":
            try:
                strategy_module = importlib.import_module(f"core.strategies.{strategy_name}")
                if not silent: print(f"🧩 전략 로딩 성공: {strategy_name}")
            except ModuleNotFoundError:
                print(f"❌ 전략 파일을 찾을 수 없습니다: {strategy_name}")
                return None

        # [2] AI 두뇌 준비
        ai_brain = None
        is_pure_ai = (strategy_name is None or strategy_name == "None")
        
        if is_pure_ai or use_ai_filter:
            if AIStrategy:
                ai_brain = AIStrategy()
                if not silent:
                    mode_msg = "🧠 [순수 AI 모드]" if is_pure_ai else "🤝 [하이브리드 모드]"
                    print(f"{mode_msg} AI가 활성화되었습니다.")
            else:
                print("❌ AIStrategy 파일이 없어 AI를 사용할 수 없습니다.")
                return None

        cash = self.initial_capital
        shares = 0
        self.trade_log = []
        self.balance_history = []

        if not silent: print(f"🚀 시뮬레이션 시작...")

        for i in range(len(df)):
            today = df.iloc[i]
            current_date_str = str(today['Date']).split('.')[0]
            
            if start_date and current_date_str < str(start_date): continue
            if end_date and current_date_str > str(end_date): break

            price = today['Close']
            date = today['Date']
            
            total_value = cash + (shares * price)
            self.balance_history.append({'Date': date, 'TotalValue': total_value})

            # --- 신호 결정 ---
            signal = 0 
            reason = ""

            if is_pure_ai:
                if not silent: print(f".", end="", flush=True)
                decision, pct, ai_reason = ai_brain.analyze_market(df, i)
                if decision == "BUY":
                    signal = 1
                    reason = f"[AI단독] {ai_reason}"
                elif decision == "SELL":
                    signal = -1
                    reason = f"[AI단독] {ai_reason}"

            elif strategy_module:
                try:
                    signal, reason = strategy_module.calculate(df, i)
                    if use_ai_filter and signal == 1:
                        decision, pct, ai_reason = ai_brain.analyze_market(df, i)
                        if decision == "BUY":
                            reason = f"[AI승인] {reason} + {ai_reason}"
                        else:
                            signal = 0 

                except Exception as e:
                    if not silent: print(f"🔥 전략 에러 ({date}): {e}")
                    signal = 0

            # --- 주문 실행 ---
            if signal == 1 and cash > price:
                buy_qty = int(cash // (price * (1 + self.fee)))
                if buy_qty > 0:
                    fee = (price * buy_qty) * self.fee
                    cash -= (price * buy_qty) + fee
                    shares += buy_qty
                    self.trade_log.append({'Date': date, 'Type': 'BUY', 'Price': price, 'Qty': buy_qty, 'Reason': reason})
                    if not silent: print(f"  🔴 BUY: {date} | {reason}")

            elif signal == -1 and shares > 0:
                amount = shares * price
                fee = amount * self.fee
                tax = amount * self.tax
                cash += amount - (fee + tax)
                self.trade_log.append({'Date': date, 'Type': 'SELL', 'Price': price, 'Qty': shares, 'Reason': reason})
                shares = 0
                if not silent: print(f"  🔵 SELL: {date} | {reason}")

        final_value = cash + (shares * df.iloc[-1]['Close'])
        return_rate = ((final_value - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'final_balance': int(final_value),
            'return_rate': round(return_rate, 2),
            'trade_count': len(self.trade_log),
            'history': pd.DataFrame(self.balance_history),
            'trade_log': self.trade_log
        }

    # ------------------------------------------------------------------
    # [추가 기능] 전체 종목 일괄 백테스트
    # ------------------------------------------------------------------
    def run_all_simulation(self, timeframe='daily', strategy_name=None, use_ai_filter=False, start_date=None, end_date=None):
        """
        데이터베이스에 있는 모든 .jsonl 파일을 찾아서 순차적으로 백테스트를 돌리고,
        결과를 요약해서 반환합니다.
        """
        # 1. 파일 목록 찾기
        folder_name = "02_daily" if timeframe == 'daily' else "03_minute"
        dir_path = os.path.join(root_path, "database", folder_name)
        
        if not os.path.exists(dir_path):
            print(f"❌ 데이터 폴더를 찾을 수 없습니다: {dir_path}")
            return None

        files = [f for f in os.listdir(dir_path) if f.endswith('.jsonl')]
        total_files = len(files)
        
        print(f"📂 총 {total_files}개의 종목을 발견했습니다. 전체 백테스트를 시작합니다...")
        print(f"⚙️ 설정: 전략={strategy_name}, AI필터={use_ai_filter}, 기간={start_date}~{end_date}")
        print("-" * 60)

        all_results = []

        # 2. 반복 실행
        for idx, filename in enumerate(files):
            code = filename.replace('.jsonl', '')
            
            # 진행률 표시
            print(f"[{idx+1}/{total_files}] {code} 테스트 중...", end=" ", flush=True)

            # 데이터 로드
            df = self.load_data(code, timeframe)
            if df is None:
                print("❌ 데이터 로드 실패")
                continue

            # 시뮬레이션 실행 (silent=True로 설정하여 개별 로그 숨김)
            # 주의: AI 모드 사용 시 시간이 매우 오래 걸릴 수 있음
            result = self.run_simulation(
                df, 
                strategy_name=strategy_name, 
                use_ai_filter=use_ai_filter, 
                start_date=start_date, 
                end_date=end_date,
                silent=True # 전체 돌릴 때는 개별 로그 끔
            )

            if result:
                print(f"✅ 수익률: {result['return_rate']}%")
                all_results.append({
                    'Code': code,
                    'Return(%)': result['return_rate'],
                    'FinalBalance': result['final_balance'],
                    'Trades': result['trade_count']
                })
            else:
                print("⚠️ 결과 없음")

        # 3. 결과 집계
        if not all_results:
            print("❌ 실행된 시뮬레이션이 없습니다.")
            return None

        summary_df = pd.DataFrame(all_results)
        
        # 수익률 순으로 정렬
        summary_df = summary_df.sort_values(by='Return(%)', ascending=False).reset_index(drop=True)
        
        print("-" * 60)
        print("📊 [전체 백테스트 결과 요약]")
        print(f"평균 수익률: {summary_df['Return(%)'].mean():.2f}%")
        print(f"최고 수익률: {summary_df.iloc[0]['Code']} ({summary_df.iloc[0]['Return(%)']}%)")
        print(f"최저 수익률: {summary_df.iloc[-1]['Code']} ({summary_df.iloc[-1]['Return(%)']}%)")
        
        return summary_df