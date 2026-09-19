"""One event loop owns reusable LLM transports; no cross-loop clients."""
import atexit
import asyncio
from threading import Lock, Thread

import httpx

from intent_hub.config import Config
from intent_hub.services.llm_factory import LLMFactory
from intent_hub.utils.route_trace import trace_event, trace_stage


class LLMRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self.loop.run_forever, name='routing-llm', daemon=True)
        self.thread.start()
        self.slot = None
        self.lock = None

    @staticmethod
    def configuration():
        with Config.LOCK:
            return (Config.LLM_PROVIDER, Config.LLM_API_KEY, Config.LLM_BASE_URL,
                    Config.LLM_MODEL, Config.LLM_FALLBACK_TIMEOUT_SECONDS)

    async def _acquire(self, config):
        if self.lock is None:
            self.lock = asyncio.Lock()
        async with self.lock:
            # Factory identity also isolates injected clients in tests.
            key = (*config, LLMFactory.create_llm)
            if self.slot is not None and self.slot['key'] == key:
                self.slot['users'] += 1
                trace_event('llm_client', reused=True)
                return self.slot
            provider, api_key, base_url, model, timeout = config
            client = None
            try:
                with trace_stage('llm_client_init'):
                    options = {}
                    if provider != 'gemini':
                        client = httpx.AsyncClient(timeout=timeout)
                        options['http_async_client'] = client
                    llm = LLMFactory.create_llm(provider=provider, api_key=api_key,
                        base_url=base_url, model=model, temperature=0, timeout=timeout,
                        max_retries=0, **options)
            except BaseException:
                if client is not None:
                    await client.aclose()
                raise
            previous = self.slot
            self.slot = {'key': key, 'llm': llm, 'client': client, 'users': 1, 'retired': False}
            if previous is not None:
                previous['retired'] = True
                if previous['users'] == 0:
                    await self._close_slot(previous)
            trace_event('llm_client', reused=False)
            return self.slot

    async def _close_slot(self, slot):
        sync_client = getattr(slot['llm'], 'root_client', None)
        if sync_client is not None:
            sync_client.close()
        if slot['client'] is not None:
            await slot['client'].aclose()

    async def _run(self, messages, config):
        slot = await self._acquire(config)
        try:
            if messages is None:
                return None
            trace_event('llm_call_started')
            with trace_stage('llm_call'):
                return await asyncio.wait_for(slot['llm'].ainvoke(messages), timeout=config[-1])
        finally:
            slot['users'] -= 1
            if slot['retired'] and slot['users'] == 0:
                await self._close_slot(slot)

    def invoke(self, messages):
        # run_coroutine_threadsafe propagates the submitting contextvars, including Flask g.
        future = asyncio.run_coroutine_threadsafe(self._run(messages, self.configuration()), self.loop)
        return future.result()

    async def _shutdown(self):
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.slot is not None:
            await self._close_slot(self.slot)
            self.slot = None

    def close(self):
        if self.loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop).result(timeout=5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()


_runtime = None
_runtime_lock = Lock()


def get_llm_runtime():
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = LLMRuntime()
            atexit.register(_runtime.close)
        return _runtime


def warm_llm():
    if Config.LLM_FALLBACK_ENABLED:
        from intent_hub.utils.logger import logger
        try:
            get_llm_runtime().invoke(None)
        except Exception as exc:
            logger.warning('LLM client warmup failed (%s)', type(exc).__name__)
