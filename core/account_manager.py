import requests
import pandas as pd

class AccountManager:
    """
    [계좌 관리자]
    - 역할: 주식 잔고 조회, 예수금 조회 등 계좌 관련 정보 처리
    - 관리: 토큰(Token), 계좌번호, 접속 URL(실전/모의) 자동 관리
    """
    def __init__(self, token, account_num, mode='2'):
        self.token = token
        self.account_num = account_num
        
        # 모드에 따른 URL 설정
        if mode == '1':  # 실전
            self.base_url = "https://openapi.koreainvestment.com:9443"
        else:            # 모의 (기본값)
            self.base_url = "https://openapivts.koreainvestment.com:29443"

        # 공통 헤더 (기본 템플릿)
        self.common_headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {self.token}',
            'cont-yn': 'N',
            'next-key': ''
        }

    # -----------------------------------------------------------
    # 1. 주식 잔고 조회 (API ID: kt00018)
    # -----------------------------------------------------------
    def get_balance(self):
        """보유 종목 및 계좌 평가 현황 조회"""
        endpoint = '/api/dostk/acnt'
        url = f"{self.base_url}{endpoint}"

        headers = self.common_headers.copy()
        headers['api-id'] = 'kt00018'

        body_data = {
            "vt_acc_no": self.account_num,
            "qry_tp": "1",
            "dmst_stex_tp": "KRX"
        }

        try:
            response = requests.post(url, headers=headers, json=body_data)
            
            if response.status_code == 200:
                res_json = response.json()
                
                # 1. 계좌 요약 정보 추출
                summary_data = {
                    "총매입금액": res_json.get("tot_pur_amt", "0"),
                    "총평가금액": res_json.get("tot_evlt_amt", "0"),
                    "총평가손익": res_json.get("tot_evlt_pl", "0"),
                    "총수익률(%)": res_json.get("tot_prft_rt", "0"),
                    "추정예탁자산": res_json.get("prsm_dpst_aset_amt", "0")
                }
                
                # 2. 정수/실수 형변환
                for key, val in summary_data.items():
                    try:
                        if key == "총수익률(%)":
                            summary_data[key] = float(val)
                        else:
                            summary_data[key] = int(val)
                    except:
                        pass

                return pd.DataFrame([summary_data])
            else:
                print(f"❌ [Balance] 에러: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ [Balance] 시스템 예외: {e}")
            return None

    # -----------------------------------------------------------
    # 2. 예수금 조회 (API ID: kt00001)
    # -----------------------------------------------------------
    def get_deposit(self):
        """주문 가능 금액 및 예수금 조회"""
        endpoint = '/api/dostk/acnt'
        url = f"{self.base_url}{endpoint}"

        headers = self.common_headers.copy()
        headers['api-id'] = 'kt00001'

        body_data = {
            "vt_acc_no": self.account_num,
            "qry_tp": "2" 
        }

        try:
            response = requests.post(url, headers=headers, json=body_data)

            if response.status_code == 200:
                res_json = response.json()
                
                data_map = {
                    "예수금": res_json.get("entr", "0"),
                    "출금가능금액": res_json.get("pymn_alow_amt", "0"),
                    "주문가능금액": res_json.get("ord_alow_amt", "0"),
                    "D+2예수금": res_json.get("d2_entra", "0")
                }
                
                for key, val in data_map.items():
                    try:
                        data_map[key] = int(val)
                    except:
                        pass


                return pd.DataFrame([data_map])

            else:
                print(f"❌ [Deposit] 에러: {response.text}")
                return None

        except Exception as e:
            print(f"❌ [Deposit] 시스템 예외: {e}")
            return None