# core/trader/__init__.py

# 1. 주문 전송 담당 (HTTP/REST)
from .order_manager import KiwoomOrderManager

# 2. 실시간 체결 통보 담당 (WebSocket)
from .execution_feed import ExecutionFeed

# 외부에서 'from core.trader import KiwoomOrderManager' 형태로 사용 가능
__all__ = [
    'KiwoomOrderManager',
    'ExecutionFeed'
]