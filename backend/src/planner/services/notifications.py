"""In-app notifications, optionally mirrored as Expo push notifications."""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.config import get_settings
from planner.db.models import Notification, PushToken

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def notify(
    db: Session, user_id: int, goal_id: int | None, type_: str, title: str, body: str, data: dict | None = None
) -> Notification:
    n = Notification(user_id=user_id, goal_id=goal_id, type=type_, title=title, body=body[:500], data=data or {})
    db.add(n)
    db.flush()
    if get_settings().push_enabled:
        tokens = db.scalars(select(PushToken.token).where(PushToken.user_id == user_id)).all()
        send_push(list(tokens), title, body, {"goal_id": goal_id, "notification_id": n.id, **(data or {})})
    return n


def send_push(tokens: list[str], title: str, body: str, data: dict) -> None:
    if not tokens:
        return
    messages = [{"to": t, "title": title, "body": body[:180], "data": data, "sound": "default"} for t in tokens]
    try:
        httpx.post(EXPO_PUSH_URL, json=messages, timeout=10).raise_for_status()
    except httpx.HTTPError:
        log.exception("push notification failed")
