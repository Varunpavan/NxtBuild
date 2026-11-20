import asyncio


class ConcurrencyManager:
    def __init__(self):
        self._active = set()
        self._lock = asyncio.Lock()

    async def acquire(self, project_id: str) -> bool:
        async with self._lock:
            if project_id in self._active:
                return False
            self._active.add(project_id)
            return True

    async def release(self, project_id: str):
        async with self._lock:
            self._active.discard(project_id)


concurrency_manager = ConcurrencyManager()
