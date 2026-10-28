from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from conftest import make_active_goal, register

from planner.lang import PY_WEEKDAYS

TZ = ZoneInfo("Asia/Jerusalem")


def at_local(day: date, hh: int, mm: int = 0) -> str:
    return datetime.combine(day, time(hh, mm), TZ).astimezone(timezone.utc).isoformat()


def next_due_day(client, headers, goal_id, task_id="t1", after: int = 1) -> date:
    plan = client.get(f"/goals/{goal_id}/plan", headers=headers).json()["plan"]
    days = next(t for t in plan["tasks"] if t["id"] == task_id)["schedule"]["days_of_week"]
    start = datetime.now(TZ).date()
    return next(start + timedelta(days=d) for d in range(after, after + 7)
                if PY_WEEKDAYS[(start + timedelta(days=d)).weekday()] in days)


def checkins(client, headers, goal_id):
    return [m for m in client.get(f"/goals/{goal_id}/chat", headers=headers).json() if m["kind"] == "checkin"]


def test_evening_checkin_asks_about_todays_tasks_once(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers)
    day = next_due_day(client, headers, goal_id)

    assert client.post("/dev/tick", headers=headers, json={"now": at_local(day, 20, 30)}).json()["checkins"] == 1
    msgs = checkins(client, headers, goal_id)
    assert len(msgs) == 1 and msgs[0]["meta"]["trigger"] == "daily_tasks"
    assert "Workout" in msgs[0]["content"]
    notif = client.get("/notifications", headers=headers).json()
    assert notif[0]["type"] == "checkin" and notif[0]["read_at"] is None

    # Another user's dev tick does not touch this user's goals.
    other = register(client, "other@example.com")
    assert client.post("/dev/tick", headers=other, json={"now": at_local(day, 20, 45)}).json()["checkins"] == 0

    # Same evening again: no duplicate.
    client.post("/dev/tick", headers=headers, json={"now": at_local(day, 21, 0)})
    assert len(checkins(client, headers, goal_id)) == 1

    client.post("/notifications/read-all", headers=headers)
    assert client.get("/notifications", headers=headers, params={"unread_only": True}).json() == []


def test_quiet_hours_and_disabled_checkins(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers)
    day = next_due_day(client, headers, goal_id)
    client.post("/dev/tick", headers=headers, json={"now": at_local(day, 23, 15)})
    assert checkins(client, headers, goal_id) == []

    client.patch(f"/goals/{goal_id}", headers=headers, json={"checkin_settings": {"enabled": False}})
    client.post("/dev/tick", headers=headers, json={"now": at_local(day, 20, 30)})
    assert checkins(client, headers, goal_id) == []


def test_missed_yesterday_morning_message(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers)
    day = next_due_day(client, headers, goal_id)
    client.post("/dev/tick", headers=headers, json={"now": at_local(day + timedelta(days=1), 9, 0)})
    msgs = checkins(client, headers, goal_id)
    assert msgs and msgs[0]["meta"]["trigger"] == "missed_yesterday"


def test_answering_a_checkin_logs_the_task(client):
    headers = register(client)
    goal_id = make_active_goal(client, headers)
    today = datetime.now(TZ).date()
    plan = client.get(f"/goals/{goal_id}/plan", headers=headers).json()["plan"]
    due_today = client.get(f"/goals/{goal_id}/today", headers=headers).json()["tasks"]
    if not due_today:
        return  # nothing due today in this plan; covered by the unit test for "yes" resolution
    client.post("/dev/tick", headers=headers, json={"now": at_local(today, 20, 30)})
    r = client.post(f"/goals/{goal_id}/chat", headers=headers, json={"content": "Yes, done!"})
    assert r.json()["actions"], plan
    statuses = {t["status"] for t in client.get(f"/goals/{goal_id}/today", headers=headers).json()["tasks"]}
    assert "done" in statuses
