"""Redis client utilities for task queue management."""

from functools import lru_cache
from uuid import UUID

import redis.asyncio as redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    """
    Get or create the Redis async client (lazy initialization).

    Returns a Redis client configured with the REDIS_URL from settings.
    """
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


async def enqueue_task(task_id: UUID, priority: int = 0) -> None:
    """
    Add a task ID to the task queue.

    Uses a Redis sorted set with priority as the score.
    Higher priority tasks (lower score) are processed first.

    Args:
        task_id: The UUID of the task to enqueue
        priority: Task priority (1-5, where 1 is highest priority)
    """
    client = get_redis_client()
    # Use negative priority so higher priority (1) comes before lower (5)
    score = priority
    await client.zadd(settings.TASK_QUEUE_NAME, {str(task_id): score})


async def dequeue_task() -> str | None:
    """
    Remove and return the highest priority task ID from the queue.

    Returns the task ID string, or None if the queue is empty.
    """
    client = get_redis_client()
    # ZPOPMIN returns the member with the lowest score (highest priority)
    result = await client.zpopmin(settings.TASK_QUEUE_NAME, count=1)
    if result:
        task_id, _ = result[0]
        return task_id
    return None


async def get_queue_length() -> int:
    """Get the number of tasks currently in the queue."""
    client = get_redis_client()
    return await client.zcard(settings.TASK_QUEUE_NAME)


async def remove_task_from_queue(task_id: UUID) -> bool:
    """
    Remove a specific task from the queue.

    Args:
        task_id: The UUID of the task to remove

    Returns:
        True if the task was removed, False if it wasn't in the queue
    """
    client = get_redis_client()
    removed = await client.zrem(settings.TASK_QUEUE_NAME, str(task_id))
    return removed > 0


async def close_redis() -> None:
    """Close the Redis connection."""
    client = get_redis_client()
    await client.close()
