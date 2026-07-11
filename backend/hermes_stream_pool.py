"""Small sticky pool for long-lived Hermes NDJSON bridge workers."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, 15)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, 9)
        except ProcessLookupError:
            pass
        await process.wait()


@dataclass(eq=False)
class _Worker:
    process: asyncio.subprocess.Process
    busy: bool = False
    conversations: set[str] = field(default_factory=set)


class HermesStreamLease:
    def __init__(self, pool: "HermesStreamPool", worker: _Worker, conversation_key: str):
        self._pool = pool
        self._worker = worker
        self.conversation_key = conversation_key
        self._released = False

    @property
    def process(self) -> asyncio.subprocess.Process:
        return self._worker.process

    @property
    def stdout(self):
        return self.process.stdout

    @property
    def returncode(self):
        return self.process.returncode

    @property
    def pid(self):
        return self.process.pid

    async def wait(self):
        return await self.process.wait()

    async def send(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None or self.process.returncode is not None:
            raise BrokenPipeError("Hermes worker is unavailable")
        self.process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        await self.process.stdin.drain()

    async def release(self, reusable: bool) -> None:
        if self._released:
            return
        self._released = True
        await self._pool.release(self._worker, reusable=reusable)


class HermesStreamPool:
    def __init__(self, command: list[str], size: int):
        self.command = list(command)
        self.size = max(1, min(8, int(size)))
        self._workers: list[_Worker] = []
        self._owners: dict[str, _Worker] = {}
        self._condition = asyncio.Condition()
        self._start_lock = asyncio.Lock()
        self._closing = False

    async def _spawn_worker(self) -> _Worker:
        command = self.command if "--worker" in self.command else [*self.command, "--worker"]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            assert process.stdout is not None
            raw = await asyncio.wait_for(process.stdout.readline(), timeout=30)
            ready = json.loads(raw.decode("utf-8"))
            if ready != {"type": "ready"}:
                raise ValueError("Hermes worker did not become ready")
        except Exception:
            await _terminate_process(process)
            raise
        return _Worker(process=process)

    async def start(self) -> None:
        async with self._start_lock:
            if self._closing:
                raise RuntimeError("Hermes worker pool is closing")
            dead = [worker for worker in self._workers if worker.process.returncode is not None]
            for worker in dead:
                self._workers.remove(worker)
                self._forget_worker(worker)
            while len(self._workers) < self.size:
                self._workers.append(await self._spawn_worker())
        async with self._condition:
            self._condition.notify_all()

    def _forget_worker(self, worker: _Worker) -> None:
        for key, owner in list(self._owners.items()):
            if owner is worker:
                self._owners.pop(key, None)

    async def acquire(self, conversation_key: str, timeout: float) -> HermesStreamLease:
        await self.start()

        async def choose() -> HermesStreamLease:
            while True:
                async with self._condition:
                    if self._closing:
                        raise RuntimeError("Hermes worker pool is closing")
                    owner = self._owners.get(conversation_key)
                    if owner and owner.process.returncode is None and not owner.busy:
                        owner.busy = True
                        return HermesStreamLease(self, owner, conversation_key)

                    available = [
                        worker
                        for worker in self._workers
                        if worker.process.returncode is None and not worker.busy
                    ]
                    if available:
                        worker = min(available, key=lambda item: len(item.conversations))
                        if owner is not None:
                            owner.conversations.discard(conversation_key)
                        self._owners[conversation_key] = worker
                        worker.conversations.add(conversation_key)
                        worker.busy = True
                        return HermesStreamLease(self, worker, conversation_key)
                    await self._condition.wait()

        return await asyncio.wait_for(choose(), timeout=timeout)

    async def release(self, worker: _Worker, reusable: bool) -> None:
        discard = not reusable or worker.process.returncode is not None
        async with self._condition:
            worker.busy = False
            if discard and worker in self._workers:
                self._workers.remove(worker)
                self._forget_worker(worker)
            self._condition.notify_all()
        if discard:
            await _terminate_process(worker.process)
            if not self._closing:
                try:
                    await self.start()
                except Exception as error:
                    # A later acquire retries startup; cleanup must still complete.
                    logger.warning("Hermes replacement worker failed to start: %s", error)

    async def close(self) -> None:
        self._closing = True
        async with self._condition:
            workers = list(self._workers)
            self._workers.clear()
            self._owners.clear()
            self._condition.notify_all()
        await asyncio.gather(*(_terminate_process(worker.process) for worker in workers))
