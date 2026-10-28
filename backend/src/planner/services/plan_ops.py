"""Apply planner.revise operations to a plan, validating the result."""

from typing import Any

from pydantic import ValidationError

from planner.llm.contracts import Metric, Milestone, Plan, PlanTask, RevisionOp

PLAN_FIELDS = {"title", "summary", "end_date", "tips", "safety_notes", "assumptions"}


class InvalidRevisionError(ValueError):
    pass


def _find(items: list[dict[str, Any]], key: str, value: str, what: str) -> int:
    for i, item in enumerate(items):
        if item.get(key) == value:
            return i
    raise InvalidRevisionError(f"{what} '{value}' does not exist")


def _merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in changes.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def apply_operations(plan: Plan, ops: list[RevisionOp]) -> Plan:
    """Return a new plan with ``ops`` applied. Raises ``InvalidRevisionError`` if any op is invalid."""
    doc = plan.model_dump(mode="json")
    removed_ids: set[str] = set()
    for n, op in enumerate(ops, 1):
        where = f"operation {n} ({op.op})"
        try:
            if op.op == "add_task":
                task = PlanTask.model_validate(op.data)
                if task.id in removed_ids or any(t["id"] == task.id for t in doc["tasks"]):
                    raise InvalidRevisionError(f"{where}: task id '{task.id}' is already used")
                doc["tasks"].append(task.model_dump(mode="json"))
            elif op.op == "update_task":
                i = _find(doc["tasks"], "id", op.target_id or "", "task")
                merged = _merge(doc["tasks"][i], {k: v for k, v in op.data.items() if k != "id"})
                doc["tasks"][i] = PlanTask.model_validate(merged).model_dump(mode="json")
            elif op.op == "remove_task":
                i = _find(doc["tasks"], "id", op.target_id or "", "task")
                removed_ids.add(doc["tasks"].pop(i)["id"])
            elif op.op == "add_milestone":
                ms = Milestone.model_validate(op.data)
                if any(m["id"] == ms.id for m in doc["milestones"]):
                    raise InvalidRevisionError(f"{where}: milestone id '{ms.id}' is already used")
                doc["milestones"].append(ms.model_dump(mode="json"))
            elif op.op == "update_milestone":
                i = _find(doc["milestones"], "id", op.target_id or "", "milestone")
                merged = _merge(doc["milestones"][i], {k: v for k, v in op.data.items() if k != "id"})
                doc["milestones"][i] = Milestone.model_validate(merged).model_dump(mode="json")
            elif op.op == "remove_milestone":
                i = _find(doc["milestones"], "id", op.target_id or "", "milestone")
                ms_id = doc["milestones"].pop(i)["id"]
                for t in doc["tasks"]:
                    if t.get("milestone_id") == ms_id:
                        t["milestone_id"] = None
            elif op.op == "add_metric":
                metric = Metric.model_validate(op.data)
                if any(m["key"] == metric.key for m in doc["metrics"]):
                    raise InvalidRevisionError(f"{where}: metric '{metric.key}' already exists")
                doc["metrics"].append(metric.model_dump(mode="json"))
            elif op.op == "update_metric":
                i = _find(doc["metrics"], "key", op.target_id or "", "metric")
                merged = _merge(doc["metrics"][i], {k: v for k, v in op.data.items() if k != "key"})
                doc["metrics"][i] = Metric.model_validate(merged).model_dump(mode="json")
            elif op.op == "update_plan":
                unknown = set(op.data) - PLAN_FIELDS
                if unknown:
                    raise InvalidRevisionError(f"{where}: cannot change plan fields {sorted(unknown)}")
                doc.update(op.data)
        except ValidationError as e:
            raise InvalidRevisionError(f"{where}: {e.errors()[0]['msg']}") from e
        except InvalidRevisionError as e:
            raise InvalidRevisionError(str(e) if str(e).startswith("operation") else f"{where}: {e}") from e
    try:
        return Plan.model_validate(doc)
    except ValidationError as e:
        raise InvalidRevisionError(f"resulting plan is invalid: {e.errors()[0]['msg']}") from e


def describe_operation(op: RevisionOp, plan: Plan) -> str:
    """Short English description, used for logs and the revision diff view."""
    names = {t.id: t.title for t in plan.tasks} | {m.id: m.title for m in plan.milestones} | {m.key: m.name for m in plan.metrics}
    target = names.get(op.target_id or "", op.target_id or "")
    if op.op.startswith("add_"):
        return f"{op.op}: {op.data.get('title') or op.data.get('name') or op.data.get('id') or op.data.get('key')}"
    if op.op.startswith("remove_"):
        return f"{op.op}: {target}"
    if op.op == "update_plan":
        return f"update_plan: {', '.join(op.data)}"
    return f"{op.op} {target}: {', '.join(op.data)}"
