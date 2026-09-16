from enum import Enum
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

app = FastAPI(title="Task Management API", version="1.0.0")


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    status: TaskStatus = TaskStatus.pending
    priority: TaskPriority = TaskPriority.medium


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None


class Task(TaskCreate):
    id: int


# In-memory store (no database needed for this assignment)
tasks: Dict[int, Task] = {}
_counter = {"next_id": 1}


def _new_id() -> int:
    task_id = _counter["next_id"]
    _counter["next_id"] += 1
    return task_id


def reset_store() -> None:
    """Clear all data. Used by the pytest fixtures."""
    tasks.clear()
    _counter["next_id"] = 1


@app.get("/")
def root():
    return {"message": "Task Management API is running"}


@app.get("/tasks", response_model=List[Task])
def list_tasks(status: Optional[TaskStatus] = None,
               priority: Optional[TaskPriority] = None):
    result = list(tasks.values())
    if status is not None:
        result = [t for t in result if t.status == status]
    if priority is not None:
        result = [t for t in result if t.priority == priority]
    return result


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate):
    task = Task(id=_new_id(), **payload.model_dump())
    tasks[task.id] = task
    return task


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, payload: TaskUpdate):
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    updated = task.model_copy(update=changes)
    tasks[task_id] = updated
    return updated


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    del tasks[task_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)
