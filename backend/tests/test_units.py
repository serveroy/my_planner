"""Unit tests for the pieces around the models: plan edits, schedules, parsing, safety."""

import json
from datetime import date, timedelta

import httpx
import pytest

from planner.lang import detect_language, find_weekdays
from planner.llm.clients import CompletionRequest, OpenAICompatClient, TaskModelConfig
from planner.llm.contracts import (
    AnswerFormat,
    ExtractInput,
    ExtractTask,
    ExtractMetric,
    ChatTurn,
    Plan,
    RevisionOp,
)
from planner.llm.gateway import ModelGateway, ModelOutputError, extract_json
from planner.llm.mock import coach as mock_coach
from planner.services import safety
from planner.services.plan_ops import InvalidRevisionError, apply_operations
from planner.services.schedule import is_due, tasks_due_on

START = date(2026, 11, 1)  # a Sunday


def make_plan(**overrides) -> Plan:
    doc = {
        "title": "Run 5k",
        "summary": "x",
        "start_date": START.isoformat(),
        "end_date": (START + timedelta(days=60)).isoformat(),
        "milestones": [{"id": "m1", "title": "Base", "target_date": (START + timedelta(days=30)).isoformat()}],
        "tasks": [
            {"id": "t1", "title": "Easy run", "milestone_id": "m1", "duration_minutes": 30,
             "schedule": {"type": "weekly", "days_of_week": ["sun", "tue", "thu"]}},
            {"id": "t2", "title": "Stretch", "schedule": {"type": "every_n_days", "interval_days": 3}},
            {"id": "t3", "title": "Time trial", "schedule": {"type": "once", "date": (START + timedelta(days=59)).isoformat()}},
        ],
        "metrics": [{"key": "longest_run_km", "name": "Longest run", "unit": "km", "baseline": 1, "target": 5}],
    }
    doc.update(overrides)
    return Plan.model_validate(doc)


# ---- plan document & edits ----------------------------------------------------------------------


def test_plan_rejects_broken_references():
    with pytest.raises(ValueError, match="unknown milestone"):
        make_plan(tasks=[{"id": "t1", "title": "x", "milestone_id": "nope", "schedule": {"type": "daily"}}])
    with pytest.raises(ValueError, match="duplicate task"):
        make_plan(tasks=[{"id": "t1", "title": "a", "schedule": {"type": "daily"}},
                         {"id": "t1", "title": "b", "schedule": {"type": "daily"}}])
    with pytest.raises(ValueError, match="days_of_week"):
        make_plan(tasks=[{"id": "t1", "title": "a", "schedule": {"type": "weekly"}}])


def test_apply_operations_happy_path():
    plan = make_plan()
    new = apply_operations(plan, [
        RevisionOp(op="update_task", target_id="t1", data={"duration_minutes": 20, "schedule": {"days_of_week": ["mon"]}}),
        RevisionOp(op="add_task", data={"id": "t4", "title": "Hill sprints", "schedule": {"type": "weekly", "days_of_week": ["fri"]}}),
        RevisionOp(op="remove_task", target_id="t2"),
        RevisionOp(op="remove_milestone", target_id="m1"),
        RevisionOp(op="update_metric", target_id="longest_run_km", data={"target": 6}),
        RevisionOp(op="update_plan", data={"summary": "updated"}),
    ])
    t1 = next(t for t in new.tasks if t.id == "t1")
    assert t1.duration_minutes == 20 and t1.schedule.days_of_week == ["mon"] and t1.schedule.type == "weekly"
    assert t1.milestone_id is None  # its milestone was removed
    assert [t.id for t in new.tasks] == ["t1", "t3", "t4"]
    assert new.metrics[0].target == 6 and new.summary == "updated"
    assert plan.tasks[0].duration_minutes == 30, "original plan is untouched"


@pytest.mark.parametrize("op", [
    RevisionOp(op="update_task", target_id="t9", data={"title": "x"}),
    RevisionOp(op="add_task", data={"id": "t1", "title": "dup", "schedule": {"type": "daily"}}),
    RevisionOp(op="add_task", data={"id": "t5", "title": "no schedule"}),
    RevisionOp(op="update_task", target_id="t1", data={"milestone_id": "ghost"}),
    RevisionOp(op="update_plan", data={"start_date": "2020-01-01"}),
    RevisionOp(op="update_task", target_id="t1", data={"duration_minutes": -5}),
])
def test_apply_operations_rejects_invalid(op):
    with pytest.raises(InvalidRevisionError):
        apply_operations(make_plan(), [op])


def test_removed_ids_are_not_reused():
    with pytest.raises(InvalidRevisionError):
        apply_operations(make_plan(), [
            RevisionOp(op="remove_task", target_id="t2"),
            RevisionOp(op="add_task", data={"id": "t2", "title": "new", "schedule": {"type": "daily"}}),
        ])


# ---- schedules ----------------------------------------------------------------------------------


def test_schedule_due_dates():
    plan = make_plan()
    t1, t2, t3 = plan.tasks
    assert is_due(t1, START, plan)  # Sunday
    assert not is_due(t1, START + timedelta(days=1), plan)  # Monday
    assert [is_due(t2, START + timedelta(days=d), plan) for d in range(7)] == [True, False, False, True, False, False, True]
    assert is_due(t3, START + timedelta(days=59), plan) and not is_due(t3, START, plan)
    assert not is_due(t1, START - timedelta(days=7), plan), "nothing is due before the plan starts"
    assert {t.id for t in tasks_due_on(plan, START)} == {"t1", "t2"}


# ---- gateway ------------------------------------------------------------------------------------


def test_extract_json_tolerates_chatter_and_fences():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": {"b": 2}} hope it helps') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        extract_json("no json here")


class FlakyClient:
    """Returns invalid output first, then valid output."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests: list[CompletionRequest] = []

    def complete(self, req):
        self.requests.append(req)
        return self.outputs.pop(0)


def _extract_input():
    return ExtractInput(today=START, weekday="sun", tasks=[ExtractTask(id="t1", title="Easy run", due_today=True)],
                        message="I ran today")


def test_gateway_retries_with_validation_error():
    client = FlakyClient(['{"events": [{"type": "bogus"}]}', '{"events": [{"type": "task_done", "task_id": "t1"}]}'])
    gw = ModelGateway({"coach.extract": TaskModelConfig(backend="openai", max_retries=1)}, clients={"openai": client})
    out = gw.extract(_extract_input())
    assert out.events[0].task_id == "t1"
    retry_msgs = client.requests[1].messages
    assert retry_msgs[-1]["role"] == "user" and "invalid" in retry_msgs[-1]["content"]


def test_gateway_gives_up_after_retries():
    client = FlakyClient(["nope", "still nope"])
    gw = ModelGateway({"coach.extract": TaskModelConfig(backend="openai", max_retries=1)}, clients={"openai": client})
    with pytest.raises(ModelOutputError):
        gw.extract(_extract_input())


def test_openai_client_sends_schema_and_model():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"events": []}'}}]})

    client = OpenAICompatClient()
    cfg = TaskModelConfig(backend="openai", base_url="http://vllm.test/v1", model="coach")
    client._clients[(cfg.base_url, cfg.timeout_seconds)] = httpx.Client(
        base_url=cfg.base_url, transport=httpx.MockTransport(handler))
    gw = ModelGateway({"coach.extract": cfg}, clients={"openai": client})
    assert gw.extract(_extract_input()).events == []
    assert seen["model"] == "coach"
    assert seen["response_format"]["type"] == "json_schema"
    assert seen["messages"][0]["role"] == "system"


# ---- language & mock extraction -----------------------------------------------------------------


def test_language_detection_and_weekdays():
    assert detect_language("שלום, מה שלומך?") == "he"
    assert detect_language("Hello there") == "en"
    assert detect_language("עשיתי run של 5k היום") == "he"
    assert find_weekdays("I can't on Tuesday or Friday") == ["tue", "fri"]
    assert find_weekdays("אני לא יכולה ביום שלישי") == ["tue"]
    assert AnswerFormat(language="auto").resolve("he").language == "he"
    assert AnswerFormat(language="en").resolve("he").language == "en"


def test_mock_extract_resolves_yes_against_question():
    inp = ExtractInput(
        today=START, weekday="sun",
        tasks=[ExtractTask(id="t1", title="Easy run", due_today=True), ExtractTask(id="t2", title="Stretch", due_today=True)],
        metrics=[ExtractMetric(key="longest_run_km", name="Longest run", unit="km")],
        recent_messages=[ChatTurn(role="assistant", content="Did you get to Easy run today?")],
        message="Yes! felt great",
    )
    events = mock_coach.extract(inp).events
    assert [(e.type, e.task_id) for e in events if e.type.startswith("task")] == [("task_done", "t1")]
    assert any(e.type == "mood" and e.mood == "positive" for e in events)

    yesterday = mock_coach.extract(inp.model_copy(update={"message": "yesterday I didn't run", "recent_messages": []})).events
    assert yesterday[0].type == "task_skipped" and yesterday[0].date == START - timedelta(days=1)


# ---- safety -------------------------------------------------------------------------------------


def test_safety_checks():
    assert safety.detect_crisis("sometimes I think about suicide")
    assert safety.detect_crisis("אני רוצה למות")
    assert not safety.detect_crisis("this workout killed me haha")
    flags = safety.check_profile("weight", {"age": 15, "height_cm": 165, "target_weight_kg": 45}, "lose weight")
    assert {f.code for f in flags} == {"minor_physical_goal", "underweight_target"}
    assert safety.check_profile("study", {"age": 15}, "pass my exam") == []
