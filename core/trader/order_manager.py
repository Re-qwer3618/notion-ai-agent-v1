import requests
import json
import hashlib
import hmac
import sys
import os
import logging
from datetime import datetime

# -----------------------------------------------------------
# [경로 설정]
# -----------------------------------------------------------
current_file = os.path.abspath(__file__)
core_trader_dir = os.path.dirname(current_file)
core_dir = os.path.dirname(core_trader_dir)
root_dir = os.path.dirname(core_dir)

if root_dir not in sys.path: sys.path.append(root_dir)
config_dir = os.path.join(root_dir, 'config')
if config_dir not in sys.path: sys.path.append(config_dir)

try:
    from config import load_secrets
except ImportError:
    def load_secrets(): return {}

# 로깅 설정
logger = logging.getLogger("OrderMgr")
logger.setLevel(logging.INFO)

class KiwoomOrderManager:
    """
    [주문 집행 담당 + 안전장치(Safety)]
    - 기능 1: HTTP REST API를 통한 주문 전송
    - 기능 2: 중복 매수 방지 및 일일 매수 종목 수 제한
    - 기능 3: Streamer와의 호환성을 위한 통합 인터페이스 제공
    """
    def __init__(self, mode='2', account_no=None):
        self.mode = mode
        self.account_no = account_no
        
        # 1. 호스트 설정
        if self.mode == '2':
            self.host = 'https://mockapi.kiwoom.com'
            logger.info("🔧 [Trader] 모의투자 주문 모드")
        else:
            self.host = 'https://api.kiwoom.com'
            logger.info("🔧 [Trader] 실전투자 주문 모드")
            
        self.endpoint = '/api/dostk/ordr'
        
        # 2. 키 정보 로드
        self.app_key = None
        self.app_secret = None
        self.access_token = None
        self._load_keys()

        # 🛡️ [안전장치 설정]
        self.max_daily_stocks = 5  # 하루 최대 매수 종목 수
        self.history_file = os.path.join(core_trader_dir, 'trading_history.json')
        self.bought_today = set()  # 오늘 매수한 종목 코드 집합
        self.today_date = datetime.now().strftime("%Y%m%d")
        
        # 프로그램 시작 시 과거 기록 로드 (재실행 대비)
        self._load_history()

    # -------------------------------------------------------
    # 🤝 [NEW] 통합 주문 인터페이스 (Streamer 연결용)
    # -------------------------------------------------------
    async def send_order(self, type, code, qty, price=0, trade_type='03'):
        """
        Streamer가 복잡한 걸 몰라도 주문을 낼 수 있게 해주는 중계 함수
        :param type: "BUY" or "SELL"
        :param trade_type: '00'(지정가), '03'(시장가). 기본값은 시장가.
        """
        if type == "BUY":
            # 동기 함수지만 HTTP 요청이므로 await 없이 호출 (비동기 래핑 필요 없음)
            return self.send_buy_order(code, qty, price, trade_type)
        elif type == "SELL":
            return self.send_sell_order(code, qty, price, trade_type)
        else:
            logger.error(f"❌ 알 수 없는 주문 타입: {type}")
            return None

    # -------------------------------------------------------
    # 🛡️ 안전장치 로직 (Safety Guard)
    # -------------------------------------------------------
    def _load_history(self):
        """파일에서 오늘 매매 기록을 불러옴"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    saved_date = data.get('date')
                    
                    # 날짜가 오늘과 같으면 기록 복구
                    if saved_date == self.today_date:
                        self.bought_today = set(data.get('bought_codes', []))
                        logger.info(f"💾 [History] 금일 매매 복원: {len(self.bought_today)}종목 ({list(self.bought_today)})")
                    else:
                        logger.info("📅 [History] 날짜가 변경되어 매매 기록을 초기화합니다.")
                        self.bought_today = set()
            except Exception as e:
                logger.error(f"⚠️ 기록 로드 실패: {e}")
                self.bought_today = set()

    def _save_history(self):
        """매매 기록을 파일에 저장"""
        try:
            data = {
                'date': self.today_date,
                'bought_codes': list(self.bought_today)
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"⚠️ 기록 저장 실패: {e}")

    def _check_safety(self, code):
        """주문 전 안전 규칙 검사"""
        current_date = datetime.now().strftime("%Y%m%d")
        if current_date != self.today_date:
            self.today_date = current_date
            self.bought_today = set()
            self._save_history()

        # 1. 중복 매수 체크
        if code in self.bought_today:
            logger.warning(f"⛔ [매수거부] 중복 진입 방지: 이미 오늘 매수한 종목입니다. ({code})")
            return False

        # 2. 종목 수 제한 체크
        if len(self.bought_today) >= self.max_daily_stocks:
            logger.warning(f"⛔ [매수거부] 일일 한도 초과: 오늘 이미 {len(self.bought_today)}종목을 매수했습니다.")
            return False
            
        return True

    # -------------------------------------------------------
    # 🛒 매수 주문 (Buy) - 안전장치 적용
    # -------------------------------------------------------
    def send_buy_order(self, code, qty, price=0, trade_type='03'):
        # [Step 1] 안전장치 검사
        if not self._check_safety(code):
            return None 

        # [Step 2] 주문 전송 (시장가인 경우 가격 0으로 설정)
        final_price = "0" if trade_type == '03' else str(price)
        
        result = self._send_order(
            api_id='kt10000',
            code=code, 
            qty=qty, 
            price=final_price, 
            trade_type=trade_type
        )
        
        # [Step 3] 성공 시 기록 업데이트
        if result and result.get('rt_cd') == '0':
            self.bought_today.add(code)
            self._save_history()
            logger.info(f"✅ [Safety] 금일 매수 목록 업데이트: {len(self.bought_today)}/{self.max_daily_stocks}")
            
        return result

    # -------------------------------------------------------
    # 📉 매도 주문 (Sell) - 매도는 제한 없음
    # -------------------------------------------------------
    def send_sell_order(self, code, qty, price=0, trade_type='03'):
        final_price = "0" if trade_type == '03' else str(price)
        return self._send_order(
            api_id='kt10001',
            code=code, 
            qty=qty, 
            price=final_price, 
            trade_type=trade_type
        )

    # -------------------------------------------------------
    # 🔑 기타 내부 메서드
    # -------------------------------------------------------
    def set_token(self, token):
        self.access_token = token

    def _load_keys(self):
        secrets = load_secrets()
        key_name = 'MOCK' if self.mode == '2' else 'REAL'
        key_info = secrets.get(key_name, {})
        self.app_key = key_info.get('APP_KEY')
        self.app_secret = key_info.get('SECRET_KEY')
        if not self.account_no:
            self.account_no = key_info.get('ACCOUNT')
        if not self.access_token:
            token_path = os.path.join(config_dir, 'ACCESS_TOKEN.txt')
            if os.path.exists(token_path):
                try:
                    with open(token_path, 'r', encoding='utf-8') as f:
                        self.access_token = f.read().strip()
                except: pass

    def _generate_hashkey(self, data: dict) -> str:
        if not self.app_secret: return ""
        json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return hmac.new(self.app_secret.encode('utf-8'), json_data.encode('utf-8'), hashlib.sha256).hexdigest()

    def _send_order(self, api_id, code, qty, price, trade_type):
        if not self.access_token or not self.app_key:
            logger.error("❌ 토큰 또는 앱키 누락")
            return None

        request_body = {
            "acc_no": self.account_no,
            "dmst_stex_tp": "KRX",
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(price),
            "trde_tp": trade_type,  # 00:지정가, 03:시장가
            "cond_uv": "0"
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.access_token}',
            'appKey': self.app_key,
            'appSecret': self.app_secret,
            'api-id': api_id,
            'custtype': 'P',
            'hashkey': self._generate_hashkey(request_body)
        }
        
        url = f"{self.host}{self.endpoint}"
        
        try:
            side = "매수" if api_id == 'kt10000' else "매도"
            type_str = "시장가" if trade_type == '03' else "지정가"
            logger.info(f"🚀 [{side}/{type_str}] {code} {qty}주 전송 중...")
            
            response = requests.post(url, headers=headers, json=request_body)
            
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get('rt_cd') == '0':
                    ord_no = res_json.get('ord_no')
                    logger.info(f"✅ 주문 접수 완료 (번호: {ord_no})")
                    return res_json
                else:
                    logger.error(f"❌ 주문 거부: {res_json.get('msg1')}")
            else:
                logger.error(f"💥 통신 실패: {response.status_code} | {response.text}")
                
        except Exception as e:
            logger.error(f"⚠️ 주문 에러: {e}")
        return None

if __name__ == "__main__":
    mgr = KiwoomOrderManager(mode='2')