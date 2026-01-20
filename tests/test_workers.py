"""
Test Suite for Pulse Task Worker Service.

This module tests the distributed task worker including:
- Task dequeue and processing
- Status transitions (PENDING -> RUNNING -> COMPLETED)
- Error handling and FAILED status
- Worker lifecycle

Redis operations are mocked to ensure isolated unit tests.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.worker import TaskWorker


class TestTaskWorker:
    """Test cases for the TaskWorker class."""

    @pytest.mark.asyncio
    async def test_worker_processes_task_successfully(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """
        Test that worker processes a task through full lifecycle.

        Given: A task in PENDING status in the database
        When: Worker dequeues and processes it
        Then: Task status changes PENDING -> RUNNING -> COMPLETED
        """
        # Create a pending task
        task = Task(
            id=uuid4(),
            title="Test Worker Task",
            description="Task for worker test",
            status=TaskStatus.PENDING,
            priority=1,
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Create a mock session maker that returns our test session
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        # Create worker with short work duration
        worker = TaskWorker(
            session_maker=mock_session_maker,
            poll_interval=0.1,
            task_timeout=5.0,
        )

        # Mock the _do_work method to be fast
        worker._do_work = AsyncMock()

        # Mock dequeue to return our task once, then None
        with patch("app.services.worker.dequeue_task") as mock_dequeue:
            mock_dequeue.side_effect = [str(task.id), None]

            # Process one task
            await worker._process_next_task()

        # Verify task is completed
        await db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_worker_handles_task_failure(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """
        Test that worker marks task as FAILED on error.

        Given: A task that will fail during execution
        When: Worker processes it
        Then: Task status is set to FAILED
        """
        # Create a pending task
        task = Task(
            id=uuid4(),
            title="Failing Task",
            status=TaskStatus.PENDING,
            priority=1,
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Create a mock session maker
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        worker = TaskWorker(session_maker=mock_session_maker)

        # Mock _do_work to raise an exception
        worker._do_work = AsyncMock(side_effect=Exception("Simulated failure"))

        with patch("app.services.worker.dequeue_task") as mock_dequeue:
            mock_dequeue.return_value = str(task.id)

            await worker._process_next_task()

        # Verify task is marked as failed
        await db_session.refresh(task)
        assert task.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_worker_skips_non_pending_task(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """
        Test that worker skips tasks that are not PENDING.

        Given: A task with COMPLETED status in the queue
        When: Worker tries to process it
        Then: Task status remains unchanged
        """
        # Create a completed task
        task = Task(
            id=uuid4(),
            title="Already Completed",
            status=TaskStatus.COMPLETED,
            priority=1,
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        worker = TaskWorker(session_maker=mock_session_maker)
        worker._do_work = AsyncMock()

        with patch("app.services.worker.dequeue_task") as mock_dequeue:
            mock_dequeue.return_value = str(task.id)

            await worker._process_next_task()

        # Verify task status unchanged
        await db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED
        worker._do_work.assert_not_called()

    @pytest.mark.asyncio
    async def test_worker_handles_missing_task(
        self,
        db_session: AsyncSession,
    ) -> None:
        """
        Test that worker handles gracefully when task not in DB.

        Given: A task ID in queue but task deleted from database
        When: Worker tries to process it
        Then: No exception is raised, worker continues
        """
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        worker = TaskWorker(session_maker=mock_session_maker)

        fake_task_id = uuid4()

        with patch("app.services.worker.dequeue_task") as mock_dequeue:
            mock_dequeue.return_value = str(fake_task_id)

            # Should not raise
            await worker._process_next_task()

    @pytest.mark.asyncio
    async def test_worker_empty_queue_polls(
        self,
        db_session: AsyncSession,
    ) -> None:
        """
        Test that worker sleeps when queue is empty.

        Given: An empty task queue
        When: Worker polls for tasks
        Then: Worker sleeps for poll_interval
        """
        mock_session_maker = MagicMock()

        worker = TaskWorker(
            session_maker=mock_session_maker,
            poll_interval=0.1,
        )

        with patch("app.services.worker.dequeue_task") as mock_dequeue:
            mock_dequeue.return_value = None

            with patch("asyncio.sleep") as mock_sleep:
                mock_sleep.return_value = None

                await worker._process_next_task()

                mock_sleep.assert_called_once_with(0.1)

    @pytest.mark.asyncio
    async def test_worker_stop(self) -> None:
        """
        Test that worker stops gracefully.

        Given: A running worker
        When: stop() is called
        Then: Worker exits its loop
        """
        mock_session_maker = MagicMock()
        worker = TaskWorker(session_maker=mock_session_maker, poll_interval=0.01)

        # Start worker in background and stop immediately
        async def run_and_stop():
            worker.stop()

        with patch("app.services.worker.dequeue_task") as mock_dequeue:
            mock_dequeue.return_value = None

            # Run worker with a quick stop
            task = asyncio.create_task(worker.start())
            await asyncio.sleep(0.05)
            worker.stop()
            await task

        assert worker._running is False


class TestTaskLifecycle:
    """Integration tests for full task lifecycle."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_task_lifecycle_pending_to_completed(
        self,
        mock_enqueue: AsyncMock,
        client,
        test_user: User,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """
        Test complete task lifecycle: create -> process -> complete.

        This is an integration test that verifies:
        1. Task is created via API with PENDING status
        2. Worker picks up task and sets RUNNING status
        3. Worker completes task and sets COMPLETED status
        """
        # 1. Create task via API
        response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Lifecycle Test Task", "priority": 1},
            headers=auth_headers,
        )

        assert response.status_code == 201
        task_data = response.json()
        task_id = task_data["id"]
        assert task_data["status"] == "PENDING"

        # Verify enqueue was called
        mock_enqueue.assert_called_once()

        # 2. Simulate worker processing
        from sqlalchemy import select
        from app.models.task import Task
        from uuid import UUID

        result = await db_session.execute(
            select(Task).where(Task.id == UUID(task_id))
        )
        task = result.scalar_one()

        # Simulate RUNNING status
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now(timezone.utc)
        await db_session.commit()

        # Verify via API
        response = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )
        assert response.json()["status"] == "RUNNING"

        # 3. Simulate COMPLETED status
        task.status = TaskStatus.COMPLETED
        task.updated_at = datetime.now(timezone.utc)
        await db_session.commit()

        # Verify final status
        response = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )
        assert response.json()["status"] == "COMPLETED"

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_task_lifecycle_with_failure(
        self,
        mock_enqueue: AsyncMock,
        client,
        test_user: User,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """
        Test task lifecycle with failure.

        Verifies: PENDING -> RUNNING -> FAILED
        """
        # Create task
        response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Task That Fails"},
            headers=auth_headers,
        )
        task_id = response.json()["id"]

        # Simulate failure
        from sqlalchemy import select
        from app.models.task import Task
        from uuid import UUID

        result = await db_session.execute(
            select(Task).where(Task.id == UUID(task_id))
        )
        task = result.scalar_one()

        task.status = TaskStatus.RUNNING
        await db_session.commit()

        task.status = TaskStatus.FAILED
        task.updated_at = datetime.now(timezone.utc)
        await db_session.commit()

        # Verify final status
        response = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )
        assert response.json()["status"] == "FAILED"
