from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.api.deps import create_token, current_user, hash_password, verify_password
from planner.api.schemas import LoginIn, PushTokenIn, RegisterIn, TokenOut, UserOut, UserPatch
from planner.db.models import PushToken, User
from planner.db.session import get_db

router = APIRouter(tags=["auth"])


def _check_tz(tz: str) -> None:
    if tz not in available_timezones():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown timezone '{tz}'")


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    _check_tz(body.timezone)
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    user = User(email=email, password_hash=hash_password(body.password), display_name=body.display_name,
                language=body.language, timezone=body.timezone)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong email or password")
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_none=True)
    if "timezone" in data:
        _check_tz(data["timezone"])
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    return user


@router.post("/me/push-tokens", status_code=204)
def add_push_token(body: PushTokenIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    exists = db.scalar(select(PushToken).where(PushToken.user_id == user.id, PushToken.token == body.token))
    if not exists:
        db.add(PushToken(user_id=user.id, token=body.token, platform=body.platform))
        db.commit()
