"""Task Pydantic schemas for request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus


class TaskCreate(BaseModel):
    """Schema for task creation."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: int = Field(default=1, ge=1, le=5)


class TaskUpdate(BaseModel):
    """Schema for task update (all fields optional)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    status: TaskStatus | None = None


class TaskResponse(BaseModel):
    """Schema for task response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: int
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Schema for paginated task list response."""

    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
