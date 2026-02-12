import asyncio

class ExecutionFeed:
    """
    [통합형 ExecutionFeed]
    - 매니저로부터 'REAL' 데이터를 받아 내 계좌 체결 내역만 필터링
    """
    def __init__(self, manager):
        self.manager = manager
        self.my_queue = None

    async def run(self):
        # 1. 구독 (REAL 패킷 안에 체결통보가 섞여 옴)
        self.my_queue = await self.manager.register(['REAL'])
        
        # 2. 데이터 소비 루프
        while True:
            data = await self.my_queue.get()
            await self.handle_chejan(data)
            self.my_queue.task_done()

    async def handle_chejan(self, data):
        try:
            items = data.get('data', [])
            for item in items:
                values = item.get('values', {})
                
                # 9203(주문번호)가 있으면 체결/잔고 데이터임
                ord_no = values.get('9203')
                if ord_no:
                    code = values.get('9001', '').replace('A', '')
                    name = values.get('302', '')
                    status = values.get('913', '') # 접수/체결
                    price = values.get('910', '0')
                    qty = values.get('911', '0')
                    
                    print(f" 🔔 [체결알림] {name}({code}) | {status} | {qty}주 @ {price}원")
        except: pass