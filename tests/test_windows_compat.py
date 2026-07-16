# tests/test_windows_compat.py
import asyncio


async def test_loop_supports_playwright_on_posix():
    from backend.api.routes import _loop_supports_playwright
    assert _loop_supports_playwright() is True


async def test_loop_safe_manager_delivers_across_threads():
    """Los broadcasts hechos desde otro hilo/loop llegan al loop del servidor."""
    from backend.api.routes import LoopSafeManager

    received = []

    class FakeManager:
        async def broadcast(self, message):
            received.append(message)

    proxy = LoopSafeManager(FakeManager(), asyncio.get_running_loop())

    def worker():
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(proxy.broadcast({"type": "log", "message": "hola"}))
        finally:
            loop.close()

    await asyncio.to_thread(worker)
    await asyncio.sleep(0.05)  # deja que el loop principal procese la corutina reenviada
    assert received == [{"type": "log", "message": "hola"}]
