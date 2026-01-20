"""Distributed task worker service."""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.redis import close_redis, dequeue_task
from app.models.task import Task, TaskStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskWorker:
    """
    Async task worker that processes tasks from the Redis queue.

    The worker runs in a continuous loop, polling for tasks and processing them.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        poll_interval: float = 1.0,
        task_timeout: float = 30.0,
    ):
        """
        Initialize the task worker.

        Args:
            session_maker: SQLAlchemy async session maker
            poll_interval: Seconds between queue polls when empty
            task_timeout: Maximum seconds for task execution
        """
        self.session_maker = session_maker
        self.poll_interval = poll_interval
        self.task_timeout = task_timeout
        self._running = False
        self._current_task_id: UUID | None = None

    async def start(self) -> None:
        """Start the worker loop."""
        self._running = True
        logger.info("Worker started, polling for tasks...")

        while self._running:
            try:
                await self._process_next_task()
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info("Worker stopped")

    def stop(self) -> None:
        """Signal the worker to stop after current task."""
        logger.info("Worker stop requested")
        self._running = False

    async def _process_next_task(self) -> None:
        """Dequeue and process the next task."""
        task_id_str = await dequeue_task()

        if not task_id_str:
            await asyncio.sleep(self.poll_interval)
            return

        task_id = UUID(task_id_str)
        self._current_task_id = task_id
        logger.info(f"Processing task {task_id}")

        async with self.session_maker() as session:
            try:
                await self._execute_task(session, task_id)
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                await self._mark_task_failed(session, task_id, str(e))

        self._current_task_id = None

    async def _execute_task(self, session: AsyncSession, task_id: UUID) -> None:
        """
        Execute a task.

        Args:
            session: Database session
            task_id: UUID of the task to execute
        """
        # Get task from database
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            logger.warning(f"Task {task_id} not found in database")
            return

        if task.status != TaskStatus.PENDING:
            logger.warning(f"Task {task_id} is not pending (status: {task.status})")
            return

        # Update status to RUNNING
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(f"Task {task_id} status: RUNNING")

        try:
            # Execute the task (simulated work)
            await self._do_work(task)

            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Task {task_id} status: COMPLETED")

        except asyncio.TimeoutError:
            raise Exception("Task execution timed out")
        except Exception as e:
            raise e

    async def _do_work(self, task: Task) -> None:
        """
        Perform the actual task work.

        This is where the real task execution logic would go.
        Currently simulates work with a sleep.

        Args:
            task: The task to execute
        """
        # Simulate work based on priority (higher priority = faster)
        work_duration = 2.0 / task.priority
        await asyncio.sleep(work_duration)

    async def _mark_task_failed(
        self, session: AsyncSession, task_id: UUID, error: str
    ) -> None:
        """Mark a task as failed with error message."""
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if task:
            task.status = TaskStatus.FAILED
            task.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Task {task_id} status: FAILED - {error}")


def create_worker() -> TaskWorker:
    """Create a configured task worker instance."""
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return TaskWorker(session_maker)


async def run_worker() -> None:
    """Run the task worker with graceful shutdown."""
    worker = create_worker()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def shutdown_handler():
        worker.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_handler)

    try:
        await worker.start()
    finally:
        await close_redis()


if __name__ == "__main__":
    asyncio.run(run_worker())
