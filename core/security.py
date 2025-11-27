import uuid
from datetime import timedelta, datetime, timezone
from typing import Any
import jwt
from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from core.config import settings
from core.database import engine
from models import BlacklistToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_refresh_token(refresh_token: str):
    payload = jwt.decode(
        refresh_token,
        settings.SECRET_KEY,
        algorithms=ALGORITHM
    )

    return payload

def secureLogout(user_id: uuid.UUID, access_token: str, refresh_token: str, session: Session):
    try:
        # Validate token format
        for t in [access_token, refresh_token]:
            if not t or len(t.split(".")) != 3:
                raise HTTPException(status_code=400, detail="Invalid token format")

        # Save tokens into blacklist table
        token_blacklist = BlacklistToken(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token
        )

        session.add(token_blacklist)
        session.commit()
        session.refresh(token_blacklist)

        return "User logged out successfully."

    except HTTPException:
        # Re-raise FastAPI HTTP exceptions
        session.rollback()
        raise

    except SQLAlchemyError as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred: {str(e)}"
        )

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error occurred: {str(e)}"
        )


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def delete_old_blacklisted_tokens():
    print("Running token cleanup task...")

    one_month_ago = datetime.now() - timedelta(days=30)

    with Session(engine) as session:
        session.exec(
            select(BlacklistToken)
            .where(BlacklistToken.created_at < one_month_ago)
        )

        old_tokens = session.exec(
            select(BlacklistToken)
            .where(BlacklistToken.created_at < one_month_ago)
        ).all()

        if old_tokens:
            for token in old_tokens:
                session.delete(token)

        session.commit()

        print(f"Deleted {len(old_tokens)} old tokens.")