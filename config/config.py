import requests
import json
import yaml
import os

# 현재 파일(config.py)이 있는 경로를 기준으로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_FILE = os.path.join(BASE_DIR, 'secrets.yaml')
TOKEN_FILE = os.path.join(BASE_DIR, 'ACCESS_TOKEN.txt')

def load_secrets():
    """
    secrets.yaml 파일에서 키 정보를 불러옵니다.
    """
    try:
        with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data
    except FileNotFoundError:
        print(f"[오류] {SECRETS_FILE} 파일을 찾을 수 없습니다.")
        return None
    except Exception as e:
        print(f"[오류] 설정 파일 로드 중 문제 발생: {e}")
        return None

def save_token(token):
    """
    발급받은 토큰을 ACCESS_TOKEN.txt 파일에 저장합니다.
    """
    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(token)
        print(f"✅ 토큰이 저장되었습니다: {TOKEN_FILE}")
    except Exception as e:
        print(f"❌ 토큰 파일 저장 실패: {e}")

def kiwoom_login(invest_type):
    """
    키움증권 REST API 로그인 프로세스
    """
    # 1. 시크릿 파일 로드
    secrets = load_secrets()
    if not secrets:
        return None

    # 2. 투자 유형에 따른 키 선택
    if invest_type == '1':
        print("\n>> [실전투자] 모드로 로그인을 시도합니다.")
        type_key = 'REAL'
        host = 'https://api.kiwoom.com'
    elif invest_type == '2':
        print("\n>> [모의투자] 모드로 로그인을 시도합니다.")
        type_key = 'MOCK'   
        host = 'https://mockapi.kiwoom.com'
    else:
        print("잘못된 입력입니다.")
        return None

    # 키 정보 가져오기
    appkey = secrets.get(type_key, {}).get('APP_KEY')
    secretkey = secrets.get(type_key, {}).get('SECRET_KEY')

    if not appkey or not secretkey:
        print(f"❌ secrets.yaml 파일에서 [{type_key}] 항목의 APP_KEY 또는 SECRET_KEY를 찾을 수 없습니다.")
        return None

    # 3. 로그인 요청
    endpoint = '/oauth2/token'
    url = host + endpoint
    headers = {'Content-Type': 'application/json;charset=UTF-8'}
    data = {
        'grant_type': 'client_credentials',
        'appkey': appkey,
        'secretkey': secretkey
    }

    # requests.post 호출
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get('return_code') in ['0', 0]:
                token = res_json.get('token')
                save_token(token)
                return token
    except Exception as e:
        print(f"로그인 요청 중 에러: {e}")
    return None