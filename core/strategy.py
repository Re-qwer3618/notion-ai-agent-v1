import json
import os

# 설정 파일 경로 (UI에서 저장한 그 파일)
CONFIG_FILE = 'master_config.json'

class StrategyManager:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        """설정 파일 로드"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 설정 로드 실패: {e}")
        
        # 파일이 없으면 기본값 반환
        return {
            "account": {"initial_capital": 100000000},
            "betting_strategy": {
                "S_Tier": {"min_score": 80, "weight": 0.30},
                "A_Tier": {"min_score": 60, "weight": 0.15},
                "B_Tier": {"min_score": 40, "weight": 0.05}
            }
        }

    def save_config(self, new_config):
        """[신규] 설정 파일 저장"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            self.config = new_config # 메모리 상의 설정도 업데이트
            return True
        except Exception as e:
            print(f"⚠️ 설정 저장 실패: {e}")
            return False

    def calculate_buy_amount(self, tier, current_price, real_deposit=None):
        """
        등급(Tier)에 따라 매수할 수량과 금액을 계산
        
        :param tier: 등급 (S, A, B)
        :param current_price: 현재 주가
        :param real_deposit: (선택) 실제 계좌의 주문가능 현금. 
                             이 값이 있으면 설정된 금액이 아무리 커도 실제 현금을 초과하지 않도록 조정함.
        """
        if tier not in ['S', 'A', 'B']:
            return 0, 0

        # 1. 설정 가져오기
        strategy = self.config.get('betting_strategy', {})
        account = self.config.get('account', {})
        
        # 2. 투자 비중 확인
        tier_key = f"{tier}_Tier"
        if tier_key not in strategy:
            return 0, 0
            
        weight = strategy[tier_key]['weight']
        
        # [백테스팅용] 설정된 운용 자본금
        setting_capital = account.get('initial_capital', 1000000)

        # 3. 목표 매수 금액 계산 (예: 1억 * 0.3 = 3천만원)
        target_amount = int(setting_capital * weight)
        
        # [실전 매매용 안전장치] 실제 예수금이 전달되었다면 한도 체크
        if real_deposit is not None:
            if target_amount > real_deposit:
                print(f"⚠️ [자금 조정] 목표({target_amount:,}원) > 실제예수금({real_deposit:,}원) -> 예수금 한도로 조정")
                target_amount = int(real_deposit * 0.98) # 미수 방지를 위해 예수금의 98%만 사용
        
        # 4. 매수 수량 계산 (금액 / 현재가)
        if current_price <= 0:
            return 0, 0
            
        qty = int(target_amount / current_price)
        
        # 최소 1주는 사야 함
        if qty < 1:
            return 0, 0
            
        return qty, target_amount

    def get_min_score(self, tier):
        """해당 등급의 최소 점수 반환"""
        strategy = self.config.get('betting_strategy', {})
        tier_key = f"{tier}_Tier"
        return strategy.get(tier_key, {}).get('min_score', 0)

# 테스트
if __name__ == "__main__":
    sm = StrategyManager()
    
    # [시나리오 1] 백테스팅 (자본금 1억 설정) -> 3천만원 매수 주문 나옴
    qty, amt = sm.calculate_buy_amount('S', 70000)
    print(f"🧪 [백테스트] S등급 매수: {qty}주 ({amt:,}원)")
    
    # [시나리오 2] 실전 매매 (실제 돈이 500만원밖에 없음) -> 500만원 한도로 줄여서 주문 나옴
    qty_real, amt_real = sm.calculate_buy_amount('S', 70000, real_deposit=5000000)
    print(f"💰 [실전매매] S등급 매수: {qty_real}주 ({amt_real:,}원)")