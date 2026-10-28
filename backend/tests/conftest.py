import os
from datetime import date, timedelta

import pytest

os.environ["PLANNER_SCHEDULER_ENABLED"] = "false"
os.environ["PLANNER_LLM_LOG_ENABLED"] = "false"
os.environ["PLANNER_MODELS_BACKEND"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from planner.db import session as db_session  # noqa: E402
from planner.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    db_session.init_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as c:
        yield c


def register(client: TestClient, email="dana@example.com", language="en", name="Dana") -> dict:
    r = client.post("/auth/register", json={"email": email, "password": "password123", "display_name": name,
                                            "language": language, "timezone": "Asia/Jerusalem"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


WEIGHT_GOAL = {
    "title": "Lose weight",
    "description": "I want to lose 6 kg before the summer",
    "current_state": "I barely exercise and snack a lot",
    "deadline": (date.today() + timedelta(days=120)).isoformat(),
    "available_time": {"minutes_per_day": 40, "days_per_week": 4},
    "answer_format": {"language": "auto", "verbosity": "concise"},
}

ANSWERS = {"age": "31", "height_cm": "170", "weight_kg": "82", "target_weight_kg": "76", "health_conditions": "none"}


def run_intake(client: TestClient, headers: dict, goal_id: int, answers: dict | None = None) -> dict:
    answers = answers or ANSWERS
    state = client.get(f"/goals/{goal_id}/intake", headers=headers).json()
    for _ in range(20):
        if state["status"] == "finished":
            return state
        q = state["current"]
        ans = answers.get(q["field"]) or (q["options"][0] if q["options"] else "not sure")
        r = client.post(f"/goals/{goal_id}/intake/answer", headers=headers, json={"turn_id": q["id"], "answer": ans})
        assert r.status_code == 200, r.text
        state = r.json()
    raise AssertionError("intake did not finish")


def make_active_goal(client: TestClient, headers: dict, goal: dict | None = None, **overrides) -> int:
    body = {**(goal or WEIGHT_GOAL), **overrides}
    r = client.post("/goals", headers=headers, json=body)
    assert r.status_code == 201, r.text
    goal_id = r.json()["id"]
    run_intake(client, headers, goal_id)
    r = client.post(f"/goals/{goal_id}/plan/generate", headers=headers)
    assert r.status_code == 200, r.text
    return goal_id
