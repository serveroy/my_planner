from datetime import date, timedelta

from conftest import WEIGHT_GOAL, make_active_goal, register, run_intake

from planner.lang import PY_WEEKDAYS


def test_register_login_me(client):
    headers = register(client)
    assert client.get("/me", headers=headers).json()["email"] == "dana@example.com"
    assert client.post("/auth/register", json={"email": "dana@example.com", "password": "password123",
                                               "display_name": "X"}).status_code == 409
    r = client.post("/auth/login", json={"email": "DANA@example.com", "password": "password123"})
    assert r.status_code == 200
    assert client.post("/auth/login", json={"email": "dana@example.com", "password": "nope-nope"}).status_code == 401
    assert client.get("/me").status_code == 401


def test_goals_are_private(client):
    a = register(client, "a@example.com")
    b = register(client, "b@example.com")
    goal_id = client.post("/goals", headers=a, json=WEIGHT_GOAL).json()["id"]
    assert client.get(f"/goals/{goal_id}", headers=b).status_code == 404
    assert client.get("/goals", headers=b).json() == []


def test_intake_is_adaptive_and_produces_profile(client):
    headers = register(client)
    goal_id = client.post("/goals", headers=headers, json=WEIGHT_GOAL).json()["id"]
    first = client.get(f"/goals/{goal_id}/intake", headers=headers).json()
    assert first["status"] == "in_progress" and first["current"]["field"] == "age"

    # A minor gets an extra safety question; a health condition triggers a doctor question.
    state = run_intake(client, headers, goal_id, {"age": "16", "health_conditions": "asthma"})
    fields = [t["field"] for t in state["history"]]
    assert "adult_involved" in fields and "doctor_approved" in fields
    assert len(fields) == len(set(fields)), "no question asked twice"
    goal = client.get(f"/goals/{goal_id}", headers=headers).json()
    assert goal["status"] == "planning"
    assert goal["profile"]["age"] == 16
    assert {f["code"] for f in goal["safety_flags"]} >= {"minor_physical_goal", "health_condition"}


def test_finish_intake_early(client):
    headers = register(client)
    goal_id = client.post("/goals", headers=headers, json=WEIGHT_GOAL).json()["id"]
    state = client.post(f"/goals/{goal_id}/intake/finish", headers=headers).json()
    assert state["status"] == "finished" and state["current"] is None


def test_full_flow_plan_chat_and_revision(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers)

    plan = client.get(f"/goals/{goal_id}/plan", headers=headers).json()
    assert plan["version"] == 1
    tasks = {t["id"]: t for t in plan["plan"]["tasks"]}
    weight = next(m for m in plan["plan"]["metrics"] if m["key"] == "weight_kg")
    assert weight["baseline"] == 82 and weight["target"] == 76

    # The coach opened the conversation when the plan was created.
    msgs = client.get(f"/goals/{goal_id}/chat", headers=headers).json()
    assert msgs[0]["kind"] == "plan_ready" and msgs[0]["role"] == "assistant"

    # Manual task logging, on the next day t1 is due.
    offset = next(d for d in range(7) if PY_WEEKDAYS[(date.today() + timedelta(days=d)).weekday()]
                  in tasks["t1"]["schedule"]["days_of_week"])
    day = (date.today() + timedelta(days=offset)).isoformat()
    r = client.post(f"/goals/{goal_id}/tasks/t1/log", headers=headers, json={"date": day, "status": "done"})
    if offset:
        assert r.status_code == 422  # future days cannot be logged
    else:
        assert next(t for t in r.json()["tasks"] if t["task_id"] == "t1")["status"] == "done"
    r = client.get(f"/goals/{goal_id}/today", headers=headers, params={"date": day})
    assert any(t["task_id"] == "t1" for t in r.json()["tasks"])

    # Chat: a metric is extracted and logged, and the reply acknowledges it.
    r = client.post(f"/goals/{goal_id}/chat", headers=headers, json={"content": "I weighed myself: 81.2 kg"})
    body = r.json()
    assert r.status_code == 200 and body["actions"] and "81.2" in body["reply"]["content"]
    prog = client.get(f"/goals/{goal_id}/progress", headers=headers).json()
    assert prog["metric_history"]["weight_kg"][-1]["value"] == 81.2

    # Chat: a new constraint -> revision proposed in "ask" mode, appears as a chat message + notification.
    blocked = tasks["t1"]["schedule"]["days_of_week"][0]
    day_name = {"sun": "Sunday", "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
                "fri": "Friday", "sat": "Saturday"}[blocked]
    r = client.post(f"/goals/{goal_id}/chat", headers=headers,
                    json={"content": f"I can't train on {day_name} anymore because of my new job"})
    assert r.json()["revision_in_progress"] is True
    assert r.json()["actions"] == [], "internal notes must not appear as user-visible actions"
    assert "preparing an updated plan" in r.json()["reply"]["content"]
    revs = client.get(f"/goals/{goal_id}/revisions", headers=headers).json()
    assert len(revs) == 1 and revs[0]["status"] == "pending" and revs[0]["changes"]
    assert client.get(f"/goals/{goal_id}", headers=headers).json()["has_pending_revision"] is True
    kinds = [m["kind"] for m in client.get(f"/goals/{goal_id}/chat", headers=headers).json()]
    assert "revision_proposal" in kinds
    notif_types = {n["type"] for n in client.get("/notifications", headers=headers).json()}
    assert "revision_proposal" in notif_types

    # Approve -> new plan version without the blocked day.
    r = client.post(f"/goals/{goal_id}/revisions/{revs[0]['id']}/approve", headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "applied"
    plan2 = client.get(f"/goals/{goal_id}/plan", headers=headers).json()
    assert plan2["version"] == 2
    assert all(blocked not in t["schedule"]["days_of_week"] for t in plan2["plan"]["tasks"])
    assert client.post(f"/goals/{goal_id}/revisions/{revs[0]['id']}/approve", headers=headers).status_code == 409
    assert len(client.get(f"/goals/{goal_id}/plan/versions", headers=headers).json()) == 2


def test_auto_update_mode_applies_immediately(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers, update_mode="auto")
    r = client.post(f"/goals/{goal_id}/revisions/request", headers=headers,
                    json={"message": "This is too hard, please make it easier"})
    assert r.status_code == 200 and r.json()["status"] == "applied"
    assert client.get(f"/goals/{goal_id}/plan", headers=headers).json()["version"] == 2
    kinds = [m["kind"] for m in client.get(f"/goals/{goal_id}/chat", headers=headers).json()]
    assert "revision_applied" in kinds


def test_reject_revision_keeps_plan(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers)
    rev = client.post(f"/goals/{goal_id}/revisions/request", headers=headers,
                      json={"message": "make it easier please"}).json()
    assert rev["status"] == "pending"
    r = client.post(f"/goals/{goal_id}/revisions/{rev['id']}/reject", headers=headers)
    assert r.json()["status"] == "rejected"
    assert client.get(f"/goals/{goal_id}/plan", headers=headers).json()["version"] == 1


def test_hebrew_goal_end_to_end(client):
    headers = register(client, language="he", name="נועה")
    goal = {**WEIGHT_GOAL, "title": "לרדת במשקל", "description": "רוצה לרדת 6 קילו עד הקיץ", "current_state": "לא מתאמנת"}
    r = client.post("/goals", headers=headers, json=goal)
    goal_id = r.json()["id"]
    q = client.get(f"/goals/{goal_id}/intake", headers=headers).json()["current"]
    assert q["question"] == "מה הגיל שלך?"
    run_intake(client, headers, goal_id)
    plan = client.post(f"/goals/{goal_id}/plan/generate", headers=headers).json()["plan"]
    assert plan["tasks"][0]["title"] == "אימון"

    r = client.post(f"/goals/{goal_id}/chat", headers=headers, json={"content": "היום התאמנתי!"})
    reply = r.json()["reply"]["content"]
    assert any("֐" <= ch <= "׿" for ch in reply)


def test_crisis_message_gets_safe_fixed_response(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers)
    r = client.post(f"/goals/{goal_id}/chat", headers=headers, json={"content": "honestly I want to die"})
    reply = r.json()["reply"]
    assert reply["kind"] == "safety" and "988" in reply["content"] and "1201" in reply["content"]
    flags = client.get(f"/goals/{goal_id}", headers=headers).json()["safety_flags"]
    assert any(f["code"] == "crisis_language" for f in flags)


def test_chat_requires_finished_intake(client):
    headers = register(client)
    goal_id = client.post("/goals", headers=headers, json=WEIGHT_GOAL).json()["id"]
    assert client.post(f"/goals/{goal_id}/chat", headers=headers, json={"content": "hi"}).status_code == 409
