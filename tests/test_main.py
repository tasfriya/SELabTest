"""Pytest suite for the Task Management API.

Covers every CRUD operation on /tasks for both successful and unsuccessful
requests. The invalid scenarios are grouped at the bottom of the file and
cover three failure modes:

  * 404 - operating on a task id that does not exist (GET / PUT / DELETE)
  * 422 - a body that fails validation (empty title, missing title,
          unknown enum value for priority or status)
  * 422 - a path parameter that is not an integer
  * 400 - a PUT with no fields to update

Each test runs against a freshly emptied store thanks to the autouse
``reset_state`` fixture, so the tests can run in any order.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app, reset_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Empty the in-memory store before and after every single test.

    Without this the id counter and the stored tasks would leak from one test
    into the next, making the suite order-dependent.
    """
    reset_store()
    yield
    reset_store()


def make_task(
    title="Write unit tests",
    description="Cover the task API with pytest",
    status="pending",
    priority="high",
):
    """Build a valid request body, overriding only what a test cares about."""
    return {
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
    }


def create_task(**overrides):
    """Create a task through the API and return the parsed response body."""
    response = client.post("/tasks", json=make_task(**overrides))
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# CREATE - POST /tasks
# ---------------------------------------------------------------------------


def test_create_task_returns_201_and_the_created_task():
    """A valid POST stores the task and echoes it back with a new id."""
    payload = make_task()

    response = client.post("/tasks", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == payload["title"]
    assert body["description"] == payload["description"]
    assert body["status"] == payload["status"]
    assert body["priority"] == payload["priority"]


def test_create_task_applies_defaults_when_optional_fields_are_omitted():
    """Only the title is required; the rest fall back to their defaults."""
    response = client.post("/tasks", json={"title": "Minimal task"})

    assert response.status_code == 201
    body = response.json()
    assert body["description"] == ""
    assert body["status"] == "pending"
    assert body["priority"] == "medium"


def test_create_task_assigns_incrementing_ids():
    """Each new task gets a distinct id rather than overwriting the last."""
    first = create_task(title="First")
    second = create_task(title="Second")

    assert first["id"] != second["id"]
    assert second["id"] == first["id"] + 1


# ---------------------------------------------------------------------------
# READ - GET /tasks and GET /tasks/{task_id}
# ---------------------------------------------------------------------------


def test_list_tasks_is_empty_before_anything_is_created():
    """A fresh store returns an empty list, not an error."""
    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_list_tasks_returns_every_created_task():
    """All created tasks show up in the collection endpoint."""
    create_task(title="Task A")
    create_task(title="Task B")

    response = client.get("/tasks")

    assert response.status_code == 200
    titles = [task["title"] for task in response.json()]
    assert titles == ["Task A", "Task B"]


def test_get_single_task_returns_the_matching_task():
    """Fetching an existing id returns exactly that task."""
    created = create_task(title="Fetch me")

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


# ---------------------------------------------------------------------------
# UPDATE - PUT /tasks/{task_id}
# ---------------------------------------------------------------------------


def test_update_task_replaces_every_field_but_keeps_the_id():
    """A successful PUT overwrites the stored task and preserves its id."""
    created = create_task(title="Old title", status="pending", priority="low")

    response = client.put(
        f"/tasks/{created['id']}",
        json=make_task(
            title="New title",
            description="Updated description",
            status="done",
            priority="high",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["title"] == "New title"
    assert body["description"] == "Updated description"
    assert body["status"] == "done"
    assert body["priority"] == "high"


def test_update_task_is_visible_on_a_later_get():
    """The update is persisted, not just reflected in the PUT response."""
    created = create_task(title="Before")

    client.put(f"/tasks/{created['id']}", json=make_task(title="After"))
    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "After"


def test_update_task_with_partial_body_only_changes_given_fields():
    """PUT is a partial update: fields left out keep their previous value."""
    created = create_task(
        title="Original title",
        description="Original description",
        status="pending",
        priority="low",
    )

    response = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["title"] == "Original title"
    assert body["description"] == "Original description"
    assert body["priority"] == "low"


# ---------------------------------------------------------------------------
# DELETE - DELETE /tasks/{task_id}
# ---------------------------------------------------------------------------


def test_delete_task_returns_204():
    """Deleting an existing task succeeds with an empty response."""
    created = create_task(title="Delete me")

    response = client.delete(f"/tasks/{created['id']}")

    assert response.status_code == 204


def test_deleted_task_can_no_longer_be_fetched():
    """After a delete the task is gone from both endpoints."""
    created = create_task(title="Delete me")

    client.delete(f"/tasks/{created['id']}")

    assert client.get(f"/tasks/{created['id']}").status_code == 404
    assert client.get("/tasks").json() == []


# ---------------------------------------------------------------------------
# INVALID SCENARIOS - unsuccessful operations
# ---------------------------------------------------------------------------


def test_get_unknown_task_returns_404():
    """Invalid scenario 1: reading an id that was never created."""
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_update_unknown_task_returns_404():
    """Invalid scenario 2: updating an id that was never created."""
    response = client.put("/tasks/999", json=make_task())

    assert response.status_code == 404


def test_delete_unknown_task_returns_404():
    """Invalid scenario 3: deleting an id that was never created."""
    response = client.delete("/tasks/999")

    assert response.status_code == 404


def test_delete_twice_returns_404_the_second_time():
    """Invalid scenario 4: the same delete is not silently accepted twice."""
    created = create_task(title="Delete me once")

    assert client.delete(f"/tasks/{created['id']}").status_code == 204
    assert client.delete(f"/tasks/{created['id']}").status_code == 404


def test_create_task_with_empty_title_returns_422():
    """Invalid scenario 5: an empty title fails the min_length constraint."""
    response = client.post("/tasks", json=make_task(title=""))

    assert response.status_code == 422


def test_create_task_without_title_returns_422():
    """Invalid scenario 6: the required title field is missing entirely."""
    response = client.post("/tasks", json={"description": "No title here"})

    assert response.status_code == 422


def test_create_task_with_invalid_priority_returns_422():
    """Invalid scenario 7: priority must be one of the enum values."""
    response = client.post("/tasks", json=make_task(priority="urgent"))

    assert response.status_code == 422


def test_create_task_with_invalid_status_returns_422():
    """Invalid scenario 8: status must be one of the enum values."""
    response = client.post("/tasks", json=make_task(status="almost_done"))

    assert response.status_code == 422


def test_update_task_with_invalid_body_returns_422():
    """Validation also guards PUT, not just POST."""
    created = create_task(title="Valid task")

    response = client.put(f"/tasks/{created['id']}", json=make_task(title=""))

    assert response.status_code == 422


def test_get_task_with_non_integer_id_returns_422():
    """A path parameter that is not an int is rejected before the handler."""
    response = client.get("/tasks/not-a-number")

    assert response.status_code == 422


def test_update_task_with_no_fields_returns_400():
    """Invalid scenario 9: an empty PUT body has nothing to change."""
    created = create_task(title="Untouched")

    response = client.put(f"/tasks/{created['id']}", json={})

    assert response.status_code == 400


def test_failed_create_does_not_change_the_store():
    """A rejected POST must not leave a partial task behind."""
    client.post("/tasks", json=make_task(title=""))

    assert client.get("/tasks").json() == []
