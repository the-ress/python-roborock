from __future__ import annotations

import asyncio
import datetime
import functools
import logging
from asyncio import AbstractEventLoop, TimerHandle
from collections.abc import MutableMapping
from typing import Any, Callable, Coroutine, Optional, Tuple, TypeVar

from roborock import RoborockException

T = TypeVar("T")
DEFAULT_TIME_ZONE: Optional[datetime.tzinfo] = datetime.datetime.now().astimezone().tzinfo


def unpack_list(value: list[T], size: int) -> list[Optional[T]]:
    return (value + [None] * size)[:size]  # type: ignore


def get_running_loop_or_create_one() -> AbstractEventLoop:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def parse_datetime_to_roborock_datetime(
    start_datetime: datetime.datetime, end_datetime: datetime.datetime
) -> Tuple[datetime.datetime, datetime.datetime]:
    now = datetime.datetime.now(DEFAULT_TIME_ZONE)
    start_datetime = start_datetime.replace(
        year=now.year, month=now.month, day=now.day, second=0, microsecond=0, tzinfo=DEFAULT_TIME_ZONE
    )
    end_datetime = end_datetime.replace(
        year=now.year, month=now.month, day=now.day, second=0, microsecond=0, tzinfo=DEFAULT_TIME_ZONE
    )
    if start_datetime > end_datetime:
        end_datetime += datetime.timedelta(days=1)
    elif end_datetime < now:
        start_datetime += datetime.timedelta(days=1)
        end_datetime += datetime.timedelta(days=1)

    return start_datetime, end_datetime


def parse_time_to_datetime(
    start_time: datetime.time, end_time: datetime.time
) -> Tuple[datetime.datetime, datetime.datetime]:
    """Help to handle time data."""
    start_datetime = datetime.datetime.now(DEFAULT_TIME_ZONE).replace(
        hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0
    )
    end_datetime = datetime.datetime.now(DEFAULT_TIME_ZONE).replace(
        hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
    )

    return parse_datetime_to_roborock_datetime(start_datetime, end_datetime)


def run_sync():
    loop = get_running_loop_or_create_one()

    def decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            return loop.run_until_complete(func(*args, **kwargs))

        return wrapped

    return decorator


class RepeatableTask:
    def __init__(self, loop: AbstractEventLoop, callback: Callable[[], Coroutine], interval: int):
        self.loop = loop
        self.callback = callback
        self.interval = interval
        self._task: Optional[TimerHandle] = None

    async def _run_task(self):
        response = None
        try:
            response = await self.callback()
        except RoborockException:
            pass
        self._task = self.loop.call_later(self.interval, self._run_task_soon)
        return response

    def _run_task_soon(self):
        asyncio.create_task(self._run_task())

    def cancel(self):
        if self._task:
            self._task.cancel()

    async def reset(self):
        self.cancel()
        return await self._run_task()


class RoborockLoggerAdapter(logging.LoggerAdapter):
    def __init__(self, prefix: str, logger: logging.Logger) -> None:
        super().__init__(logger, {})
        self.prefix = prefix

    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        return "[%s] %s" % (self.prefix, msg), kwargs
