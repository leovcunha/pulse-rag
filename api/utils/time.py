import time
import asyncio
import functools
from typing import Any, Callable, Tuple

def time_it(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator that measures the execution time of a function in milliseconds.
    Returns a tuple of (function_result, duration_ms).
    Supports both synchronous and asynchronous functions.
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Tuple[Any, float]:
            start_time = time.perf_counter()
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return result, duration_ms
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Tuple[Any, float]:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return result, duration_ms
        return sync_wrapper
