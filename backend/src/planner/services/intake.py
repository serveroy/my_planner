"""Intake interview: ask planner.interview for the next question until it has enough to plan."""

from sqlalchemy.orm import Session

from planner.config import get_settings
from planner.db.models import Goal, IntakeTurn, User, utcnow
from planner.llm.contracts import InterviewInput, InterviewOutput
from planner.llm.gateway import ModelGateway
from planner.services import safety
from planner.services.context import goal_brief, qa_history, response_style, safety_flags
from planner.services.timeutil import local_today
from planner.textutil import detect_domain


class IntakeError(ValueError):
    pass


def current_turn(goal: Goal) -> IntakeTurn | None:
    return next((t for t in goal.intake_turns if t.answer is None and not t.skipped), None)


def _ask_model(db: Session, goal: Goal, user: User, gw: ModelGateway, force_finish: bool = False) -> InterviewOutput:
    asked = len(goal.intake_turns)
    remaining = 0 if force_finish else max(get_settings().intake_max_questions - asked, 0)
    inp = InterviewInput(
        today=local_today(user),
        goal=goal_brief(goal),
        style=response_style(goal, user),
        qa_history=qa_history(goal),
        questions_remaining=remaining,
        safety_flags=safety_flags(goal),
    )
    out = gw.interview(inp)
    if out.action == "ask" and (remaining == 0 or out.field in {t.field for t in goal.intake_turns}):
        # Out of budget, or the model is repeating itself: ask it to wrap up.
        if force_finish:
            return InterviewOutput(action="finish", profile={}, summary="")
        return _ask_model(db, goal, user, gw, force_finish=True)
    return out


def _finalize(db: Session, goal: Goal, user: User, out: InterviewOutput) -> None:
    profile = dict(out.profile)
    for turn in goal.intake_turns:  # keep raw answers the model didn't normalize
        if turn.answer is not None and turn.field not in profile:
            profile[turn.field] = turn.answer
    goal.profile = profile
    goal.intake_summary = out.summary or ""
    domain = str(profile.get("domain") or detect_domain(goal_brief(goal)))
    goal.safety_flags = safety.merge_flags(
        goal.safety_flags or [],
        safety.check_profile(domain, profile, f"{goal.title} {goal.description} {goal.current_state}"),
    )
    goal.status = "planning"


def advance(db: Session, goal: Goal, user: User, gw: ModelGateway) -> IntakeTurn | None:
    """Return the open question, asking the model for a new one if needed. ``None`` = intake finished."""
    if goal.status != "intake":
        return None
    if turn := current_turn(goal):
        return turn
    out = _ask_model(db, goal, user, gw)
    if out.action == "finish":
        _finalize(db, goal, user, out)
        db.commit()
        return None
    turn = IntakeTurn(
        goal_id=goal.id,
        index=len(goal.intake_turns),
        question=out.question or "",
        field=out.field or f"q{len(goal.intake_turns)}",
        answer_type=out.answer_type,
        options=out.options,
        unit=out.unit,
        reason=out.reason,
    )
    goal.intake_turns.append(turn)
    db.commit()
    return turn


def answer(db: Session, goal: Goal, user: User, gw: ModelGateway, turn_id: int, text: str | None, skip: bool = False) -> IntakeTurn | None:
    turn = current_turn(goal)
    if goal.status != "intake" or turn is None or turn.id != turn_id:
        raise IntakeError("this question is not open")
    if not skip and not (text or "").strip():
        raise IntakeError("answer is empty")
    if skip:
        turn.skipped = True
    else:
        turn.answer = text.strip()  # type: ignore[union-attr]
        if safety.detect_crisis(turn.answer):
            goal.safety_flags = safety.merge_flags(goal.safety_flags or [], [safety.crisis_flag()])
    turn.answered_at = utcnow()
    db.commit()
    return advance(db, goal, user, gw)


def finish_now(db: Session, goal: Goal, user: User, gw: ModelGateway) -> None:
    """The user wants to stop answering and get the plan."""
    if goal.status != "intake":
        return
    if turn := current_turn(goal):
        goal.intake_turns.remove(turn)
        db.delete(turn)
        db.flush()
    _finalize(db, goal, user, _ask_model(db, goal, user, gw, force_finish=True))
    db.commit()
