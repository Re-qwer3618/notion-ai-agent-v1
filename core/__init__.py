# core/__init__.py

# 1. 통신 심장 (Connection Manager)
from .connection_manager import KiwoomWebSocketManager

# 2. AI 및 전략 도구
from .ai_strategy import AIStrategy
from .strategy import StrategyManager
from .llm_connector import LLMConnector      # (확인됨: 파일 내 클래스명 LLMConnector)
from .analysis_tool import ChartTranslator   # (확인됨: 파일 내 클래스명 ChartTranslator)

# 3. 계좌 관리 및 백테스팅
from .account_manager import AccountManager  # [주의] account_manager.py를 클래스 버전으로 업데이트해야 함
from .backtester import Backtester

# 외부에서 'from core import ...' 만으로 주요 클래스를 사용할 수 있게 됩니다.
__all__ = [
    'KiwoomWebSocketManager',
    'AIStrategy',
    'StrategyManager',
    'LLMConnector',
    'ChartTranslator',
    'AccountManager',
    'Backtester'
]