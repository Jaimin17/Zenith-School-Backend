from datetime import timedelta
from typing import Any

from deps import CurrentUser
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from core.database import SessionDep
from core.security import verify_password, create_access_token
from models import User
from schemas import Token, UserPublic

router = APIRouter(
    prefix="/login"
)


def get_user_by_username(username: str, session: Session) -> User | None:
    statement = select(User).where(User.username == username)
    session_user = session.exec(statement).first()
    return session_user



@router.post("/access-token", response_model=Token)
def login_access_token(session: SessionDep, request: OAuth2PasswordRequestForm = Depends()):
    db_user = get_user_by_username(request.username, session)
    if not db_user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not verify_password(request.password, db_user.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not db_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token = create_access_token(subject={"sub": db_user.username})
    return Token(access_token=access_token, token_type="bearer")

@router.post("/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    return current_user