"""
Test Suite for Redis Queue Operations.

Tests the Redis-based task queue functionality including:
- Task enqueueing with priority
- Task dequeuing (FIFO within priority)
- Queue length checking
- Task removal from queue
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestEnqueueTask:
    """Test cases for the enqueue_task function."""

    @pytest.mark.asyncio
    async def test_enqueue_task_default_priority(self) -> None:
        """
        Test enqueueing a task with default priority.

        Given: A task ID
        When: enqueue_task is called without priority
        Then: Task is added to Redis sorted set with score 0
        """
        from app.core.redis import enqueue_task

        task_id = uuid4()

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await enqueue_task(task_id)

            mock_client.zadd.assert_called_once()
            call_args = mock_client.zadd.call_args
            assert str(task_id) in call_args[0][1]
            assert call_args[0][1][str(task_id)] == 0

    @pytest.mark.asyncio
    async def test_enqueue_task_with_priority(self) -> None:
        """
        Test enqueueing a task with specific priority.

        Given: A task ID and priority 3
        When: enqueue_task is called
        Then: Task is added with score 3
        """
        from app.core.redis import enqueue_task

        task_id = uuid4()

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await enqueue_task(task_id, priority=3)

            call_args = mock_client.zadd.call_args
            assert call_args[0][1][str(task_id)] == 3

    @pytest.mark.asyncio
    async def test_enqueue_task_high_priority(self) -> None:
        """
        Test enqueueing a high priority task.

        Given: A task with priority 1 (highest)
        When: enqueue_task is called
        Then: Task gets lowest score for earliest processing
        """
        from app.core.redis import enqueue_task

        task_id = uuid4()

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await enqueue_task(task_id, priority=1)

            call_args = mock_client.zadd.call_args
            assert call_args[0][1][str(task_id)] == 1


class TestDequeueTask:
    """Test cases for the dequeue_task function."""

    @pytest.mark.asyncio
    async def test_dequeue_task_returns_task_id(self) -> None:
        """
        Test dequeuing returns the task ID string.

        Given: A task in the queue
        When: dequeue_task is called
        Then: Returns the task ID string
        """
        from app.core.redis import dequeue_task

        task_id = str(uuid4())

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.zpopmin.return_value = [(task_id, 1.0)]
            mock_get_client.return_value = mock_client

            result = await dequeue_task()

            assert result == task_id
            mock_client.zpopmin.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_task_empty_queue(self) -> None:
        """
        Test dequeuing from empty queue returns None.

        Given: An empty task queue
        When: dequeue_task is called
        Then: Returns None
        """
        from app.core.redis import dequeue_task

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.zpopmin.return_value = []
            mock_get_client.return_value = mock_client

            result = await dequeue_task()

            assert result is None


class TestGetQueueLength:
    """Test cases for the get_queue_length function."""

    @pytest.mark.asyncio
    async def test_get_queue_length_with_tasks(self) -> None:
        """
        Test getting queue length when tasks exist.

        Given: 5 tasks in the queue
        When: get_queue_length is called
        Then: Returns 5
        """
        from app.core.redis import get_queue_length

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.zcard.return_value = 5
            mock_get_client.return_value = mock_client

            result = await get_queue_length()

            assert result == 5

    @pytest.mark.asyncio
    async def test_get_queue_length_empty(self) -> None:
        """
        Test getting queue length when empty.

        Given: An empty queue
        When: get_queue_length is called
        Then: Returns 0
        """
        from app.core.redis import get_queue_length

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.zcard.return_value = 0
            mock_get_client.return_value = mock_client

            result = await get_queue_length()

            assert result == 0


class TestRemoveTaskFromQueue:
    """Test cases for the remove_task_from_queue function."""

    @pytest.mark.asyncio
    async def test_remove_task_success(self) -> None:
        """
        Test removing an existing task from queue.

        Given: A task in the queue
        When: remove_task_from_queue is called
        Then: Returns True
        """
        from app.core.redis import remove_task_from_queue

        task_id = uuid4()

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.zrem.return_value = 1
            mock_get_client.return_value = mock_client

            result = await remove_task_from_queue(task_id)

            assert result is True
            mock_client.zrem.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_task_not_found(self) -> None:
        """
        Test removing a non-existent task from queue.

        Given: A task ID not in the queue
        When: remove_task_from_queue is called
        Then: Returns False
        """
        from app.core.redis import remove_task_from_queue

        task_id = uuid4()

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.zrem.return_value = 0
            mock_get_client.return_value = mock_client

            result = await remove_task_from_queue(task_id)

            assert result is False


class TestCloseRedis:
    """Test cases for the close_redis function."""

    @pytest.mark.asyncio
    async def test_close_redis(self) -> None:
        """
        Test closing Redis connection.

        Given: An active Redis client
        When: close_redis is called
        Then: Client close method is called
        """
        from app.core.redis import close_redis

        with patch("app.core.redis.get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await close_redis()

            mock_client.close.assert_called_once()
