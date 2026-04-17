from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable


@dataclass
class ScheduledJob:
    name: str
    interval_seconds: int
    func: Callable[[], None]
    stop_event: threading.Event
    thread: threading.Thread


class Scheduler:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._jobs: dict[str, ScheduledJob] = {}

    def every(self, name: str, interval_seconds: int, func: Callable[[], None]) -> None:
        if name in self._jobs:
            raise ValueError(f"Job already exists: {name}")

        stop_event = threading.Event()

        def loop() -> None:
            while not stop_event.is_set():
                try:
                    func()
                except Exception as exc:
                    self._logger.exception("Scheduled job %s failed: %s", name, exc)
                stop_event.wait(interval_seconds)

        thread = threading.Thread(target=loop, name=f"job:{name}", daemon=True)
        job = ScheduledJob(
            name=name,
            interval_seconds=interval_seconds,
            func=func,
            stop_event=stop_event,
            thread=thread,
        )
        self._jobs[name] = job
        thread.start()

    def cancel(self, name: str) -> None:
        job = self._jobs.pop(name, None)
        if job is None:
            return
        job.stop_event.set()
        job.thread.join(timeout=2)

    def cancel_all(self) -> None:
        for name in list(self._jobs.keys()):
            self.cancel(name)
