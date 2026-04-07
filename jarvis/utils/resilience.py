import asyncio
import logging
import random
from typing import TypeVar, Callable, Any, Awaitable, List, Type, Optional

T = TypeVar("T")

logger = logging.getLogger(__name__)

async def retry_async(
    func: Callable[..., Awaitable[T]],
    max_retries: int = 3,
    initial_delay: float = 2.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on_exceptions: List[Type[Exception]] = [Exception],
    on_retry_callback: Optional[Callable[[int, int, Exception], Awaitable[None]]] = None,
    *args,
    **kwargs
) -> T:
    """Perform an asynchronous task with exponential backoff retries.
    
    Useful for handling transient 503 (Unavailable) or 429 (Rate Limit) errors
    from cloud APIs.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if we should retry based on the exception type
            if not any(isinstance(e, ex_type) for ex_type in retry_on_exceptions):
                raise e

            if attempt == max_retries:
                logger.error(f"Execution failed after {max_retries} retries: {e}")
                raise e

            # Inform user/system of retry
            if on_retry_callback:
                await on_retry_callback(attempt + 1, max_retries, e)
            
            # Calculate next delay
            sleep_time = delay
            if jitter:
                sleep_time *= (0.5 + random.random())
            
            logger.warning(f"Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f}s... (Error: {e})")
            await asyncio.sleep(sleep_time)
            delay *= exponential_base

    if last_exception:
        raise last_exception
    raise Exception("Unknown error in retry_async")
