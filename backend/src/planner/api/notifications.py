from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from planner.api.deps import current_user, gateway
from planner.api.schemas import NotificationOut, TickIn
from planner.config import get_settings
from planner.db.models import Notification, User, utcnow
from planner.db.session import get_db, new_session
from planner.llm.gateway import ModelGateway
from planner.services import checkins

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(user: User = Depends(current_user), db: Session = Depends(get_db),
                       unread_only: bool = False, limit: int = Query(50, le=200)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    return db.scalars(q.order_by(Notification.id.desc()).limit(limit)).all()


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")
    n.read_at = n.read_at or utcnow()
    db.commit()


@router.post("/notifications/read-all", status_code=204)
def mark_all_read(user: User = Depends(current_user), db: Session = Depends(get_db), goal_id: int | None = None):
    q = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if goal_id is not None:
        q = q.where(Notification.goal_id == goal_id)
    db.execute(q.values(read_at=utcnow()))
    db.commit()


@router.post("/dev/tick", tags=["dev"])
def dev_tick(body: TickIn, user: User = Depends(current_user), gw: ModelGateway = Depends(gateway)):
    """Run one scheduler pass over the caller's goals now (optionally pretending it is ``now``)."""
    if not get_settings().dev_endpoints_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return checkins.tick(gw, new_session, body.now, user_id=user.id)
