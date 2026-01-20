"""
Test Suite for Pulse Task Management API.

This module tests the task CRUD operations including:
- Task creation with Redis queue integration
- Task listing with pagination
- Task retrieval
- Task update
- Task deletion

Redis operations are mocked to ensure isolated unit tests.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.models.task import Task, TaskStatus
from app.models.user import User


class TestTaskCreate:
    """Test cases for POST /api/v1/tasks/ endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_create_task_success(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test successful task creation.

        Given: An authenticated user
        When: POST /api/v1/tasks/ with valid task data
        Then: Task is created with PENDING status and enqueued
        """
        task_data = {
            "title": "Test Task",
            "description": "A test task description",
            "priority": 3,
        }

        response = await client.post(
            "/api/v1/tasks/",
            json=task_data,
            headers=auth_headers,
        )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}"

        data = response.json()
        assert data["title"] == task_data["title"]
        assert data["description"] == task_data["description"]
        assert data["priority"] == task_data["priority"]
        assert data["status"] == "PENDING"
        assert data["owner_id"] == str(test_user.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Verify task was enqueued
        mock_enqueue.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_create_task_default_priority(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test task creation with default priority."""
        task_data = {"title": "Task with default priority"}

        response = await client.post(
            "/api/v1/tasks/",
            json=task_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["priority"] == 1  # Default priority

    @pytest.mark.asyncio
    async def test_create_task_unauthorized(self, client: AsyncClient) -> None:
        """Test task creation without authentication."""
        task_data = {"title": "Unauthorized Task"}

        response = await client.post("/api/v1/tasks/", json=task_data)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_task_invalid_priority(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test task creation with invalid priority."""
        # Priority too high
        response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Test", "priority": 10},
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Priority too low
        response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Test", "priority": 0},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_empty_title(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test task creation with empty title."""
        response = await client.post(
            "/api/v1/tasks/",
            json={"title": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestTaskList:
    """Test cases for GET /api/v1/tasks/ endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_list_tasks_success(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test listing user's tasks."""
        # Create a few tasks
        for i in range(3):
            await client.post(
                "/api/v1/tasks/",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )

        response = await client.get("/api/v1/tasks/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_list_tasks_pagination(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test task listing with pagination."""
        # Create 5 tasks
        for i in range(5):
            await client.post(
                "/api/v1/tasks/",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )

        # Get first page with page_size=2
        response = await client.get(
            "/api/v1/tasks/",
            params={"page": 1, "page_size": 2},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2

        # Get second page
        response = await client.get(
            "/api/v1/tasks/",
            params={"page": 2, "page_size": 2},
            headers=auth_headers,
        )

        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2

    @pytest.mark.asyncio
    async def test_list_tasks_empty(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test listing tasks when none exist."""
        response = await client.get("/api/v1/tasks/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_tasks_unauthorized(self, client: AsyncClient) -> None:
        """Test listing tasks without authentication."""
        response = await client.get("/api/v1/tasks/")
        assert response.status_code == 401


class TestTaskGet:
    """Test cases for GET /api/v1/tasks/{id} endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_get_task_success(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test getting a specific task."""
        # Create a task
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Task to retrieve", "description": "Details here"},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Get the task
        response = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["title"] == "Task to retrieve"
        assert data["description"] == "Details here"

    @pytest.mark.asyncio
    async def test_get_task_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test getting a non-existent task."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/tasks/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_get_task_other_user(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        superuser: User,
        auth_headers: dict[str, str],
        db_session,
    ) -> None:
        """Test that users cannot access other users' tasks."""
        from app.core.security import create_access_token

        # Create task as test_user
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Private task"},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Try to access as superuser
        superuser_token = create_access_token(subject=str(superuser.id))
        superuser_headers = {"Authorization": f"Bearer {superuser_token}"}

        response = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers=superuser_headers,
        )
        assert response.status_code == 404  # Not found for other users


class TestTaskUpdate:
    """Test cases for PATCH /api/v1/tasks/{id} endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_update_task_success(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test updating a task."""
        # Create a task
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Original title", "priority": 1},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Update the task
        response = await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "Updated title", "priority": 5},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated title"
        assert data["priority"] == 5

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_update_task_partial(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test partial task update."""
        # Create a task
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Original", "description": "Keep this"},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Update only title
        response = await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "Updated"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["description"] == "Keep this"

    @pytest.mark.asyncio
    async def test_update_task_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test updating a non-existent task."""
        fake_id = uuid4()
        response = await client.patch(
            f"/api/v1/tasks/{fake_id}",
            json={"title": "Won't work"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestTaskDelete:
    """Test cases for DELETE /api/v1/tasks/{id} endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.remove_task_from_queue", new_callable=AsyncMock)
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_delete_task_success(
        self,
        mock_enqueue: AsyncMock,
        mock_remove: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test deleting a task."""
        # Create a task
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Task to delete"},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Delete the task
        response = await client.delete(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify task is removed from queue
        mock_remove.assert_called_once()

        # Verify task no longer exists
        get_response = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test deleting a non-existent task."""
        fake_id = uuid4()
        response = await client.delete(
            f"/api/v1/tasks/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_unauthorized(self, client: AsyncClient) -> None:
        """Test deleting task without authentication."""
        fake_id = uuid4()
        response = await client.delete(f"/api/v1/tasks/{fake_id}")
        assert response.status_code == 401


class TestTaskStatusFilter:
    """Test cases for task status filtering."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_list_tasks_filter_by_status(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session,
    ) -> None:
        """Test filtering tasks by status."""
        from uuid import UUID

        # Create tasks
        for i in range(3):
            await client.post(
                "/api/v1/tasks/",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )

        # Manually set one task to COMPLETED
        response = await client.get("/api/v1/tasks/", headers=auth_headers)
        tasks = response.json()["items"]

        from sqlalchemy import select
        from app.models.task import Task

        result = await db_session.execute(
            select(Task).where(Task.id == UUID(tasks[0]["id"]))
        )
        task = result.scalar_one()
        task.status = TaskStatus.COMPLETED
        await db_session.commit()

        # Filter by PENDING
        response = await client.get(
            "/api/v1/tasks/",
            params={"status": "PENDING"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "PENDING"

        # Filter by COMPLETED
        response = await client.get(
            "/api/v1/tasks/",
            params={"status": "COMPLETED"},
            headers=auth_headers,
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "COMPLETED"


class TestTaskRunningConstraints:
    """Test cases for running task constraints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_cannot_update_running_task(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session,
    ) -> None:
        """Test that running tasks cannot be updated."""
        from uuid import UUID

        # Create a task
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Running task"},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Set task to RUNNING
        from sqlalchemy import select
        from app.models.task import Task

        result = await db_session.execute(
            select(Task).where(Task.id == UUID(task_id))
        )
        task = result.scalar_one()
        task.status = TaskStatus.RUNNING
        await db_session.commit()

        # Try to update - should fail
        response = await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "New title"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "running" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_cannot_delete_running_task(
        self,
        mock_enqueue: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session,
    ) -> None:
        """Test that running tasks cannot be deleted."""
        from uuid import UUID

        # Create a task
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Running task"},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Set task to RUNNING
        from sqlalchemy import select
        from app.models.task import Task

        result = await db_session.execute(
            select(Task).where(Task.id == UUID(task_id))
        )
        task = result.scalar_one()
        task.status = TaskStatus.RUNNING
        await db_session.commit()

        # Try to delete - should fail
        response = await client.delete(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "running" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.api.v1.tasks.remove_task_from_queue", new_callable=AsyncMock)
    @patch("app.api.v1.tasks.enqueue_task", new_callable=AsyncMock)
    async def test_delete_completed_task_no_queue_removal(
        self,
        mock_enqueue: AsyncMock,
        mock_remove: AsyncMock,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
        db_session,
    ) -> None:
        """Test that deleting a completed task doesn't try to remove from queue."""
        from uuid import UUID

        # Create a task
        create_response = await client.post(
            "/api/v1/tasks/",
            json={"title": "Completed task"},
            headers=auth_headers,
        )
        task_id = create_response.json()["id"]

        # Set task to COMPLETED
        from sqlalchemy import select
        from app.models.task import Task

        result = await db_session.execute(
            select(Task).where(Task.id == UUID(task_id))
        )
        task = result.scalar_one()
        task.status = TaskStatus.COMPLETED
        await db_session.commit()

        # Delete the task
        response = await client.delete(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # remove_task_from_queue should NOT be called for completed tasks
        mock_remove.assert_not_called()
