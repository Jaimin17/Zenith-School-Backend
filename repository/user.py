from fastapi import HTTPException
from sqlmodel import Session

from core.security import get_password_hash
from models import User
from schemas import RegisterUser


def register_user(request: RegisterUser, session: Session) -> User:
    db_user = User(
        username=request.username,
        email=request.email,
        first_name=request.firstName,
        last_name=request.lastName,
        password=request.password
    )

    db_user =  User.model_validate(
        db_user,
        update={
            "password": get_password_hash(request.password)
        }
    )

    exist_user = session.query(User).filter(User.username == db_user.username).first()
    if exist_user:
        raise HTTPException(
            status_code=400,
            detail=f"User {db_user.username} already exists"
        )


    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user