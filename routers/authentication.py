from datetime import timedelta, date, datetime
from enum import Enum
from math import dist
from typing import Any, Union

from jwt import PyJWTError
from core.config import settings
from deps import CurrentUser, UserRole, AdminUser, TeacherOrAdminUser, AllUser, TokenDep
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from core.database import SessionDep
from core.security import verify_password, create_access_token, create_refresh_token, decode_refresh_token, secureLogout
from models import User, Admin, Teacher, Parent, Student, BlacklistToken
from schemas import Token, UserPublic, RefreshTokenRequest, TokenWithUser, AdminResponse, ParentResponse, \
    TeacherResponse, StudentResponse

router = APIRouter(
    prefix="/auth"
)


def format_user_response(user: Union[Admin, Teacher, Parent, Student], role: str) -> dict:
    if role == "admin":
        return AdminResponse.model_validate(user).model_dump(mode='json')
    elif role == "parent":
        return ParentResponse.model_validate(user).model_dump(mode='json')
    elif role == "teacher":
        return TeacherResponse.model_validate(user).model_dump(mode='json')
    elif role == "student":
        return StudentResponse.model_validate(user).model_dump(mode='json')
    return {}


def get_user_by_username(username: str, session: Session) -> tuple[Union[Admin, Teacher, Parent, Student], str] | None:
    """
        Search for a user across all role tables.
        Returns a tuple of (user_object, role_name) or None if not found.
    """
    # Check Admin
    admin = session.exec(select(Admin).where(Admin.username == username)).first()
    if admin:
        return (admin, "admin")

    # Check Parent
    parent = session.exec(select(Parent).where(Parent.username == username)).first()
    if parent:
        return (parent, "parent")

    # Check Teacher
    teacher = session.exec(select(Teacher).where(Teacher.username == username)).first()
    if teacher:
        return (teacher, "teacher")

    # Check Student
    student = session.exec(select(Student).where(Student.username == username)).first()
    if student:
        return (student, "student")

    # statement = select(User).where(User.username == username)
    # session_user = session.exec(statement).first()
    # return session_user

    return None


@router.post("/access-token", response_model=TokenWithUser)
def login_access_token(
        session: SessionDep,
        request: OAuth2PasswordRequestForm = Depends()
):
    user_data = get_user_by_username(request.username, session)

    if not user_data:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    db_user, role = user_data

    if not verify_password(request.password, db_user.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    if role != "admin" and getattr(db_user, "is_delete", False):
        raise HTTPException(status_code=400, detail="Inactive user")

    payload = {
        "sub": db_user.username,
        "user_id": str(db_user.id),
        "role": role
    }

    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    user_response = format_user_response(db_user, role)

    return TokenWithUser(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_response,
        role=role
    )


@router.post("/refresh", response_model=Token)
def refresh_access_token(data: RefreshTokenRequest):
    refresh_token = data.refresh_token

    try:
        payload = decode_refresh_token(refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        username = payload.get("sub")
        user_id = payload.get("user_id")
        role = payload.get("role")

        if username is None or user_id is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access_token = create_access_token({
        "sub": username,
        "user_id": user_id,
        "role": role
    })

    return Token(
        access_token=new_access_token,
        refresh_token=refresh_token,  # keep same refresh token
        token_type="bearer"
    )


@router.post("/logout", response_model=str)
def logout(current_user: AllUser, token: TokenDep, request: RefreshTokenRequest, session: SessionDep):
    access_token = token
    refresh_token = request.refresh_token

    db_user, role = current_user

    if not access_token:
        raise HTTPException(status_code=400, detail="Access token is required")

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token is required")

    return secureLogout(db_user.id, access_token, refresh_token, session)


@router.get("/getUserDetail", response_model=dict)
def getUserDetail(current_user: AllUser, session: SessionDep):
    db_user, role = current_user

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    user_response = format_user_response(db_user, role)
    return user_response

# @router.post("/test-token", response_model=UserPublic)
# def test_token(current_user: CurrentUser) -> Any:
#     return current_user
#
# # Example usage in routes:
# @router.get("/admin-only")
# def admin_only_route(
#     current_user: AdminUser
# ):
#     user, role = current_user
#     return {"message": "Admin access granted", "user": user.username}
#
#
# @router.get("/teacher-or-admin")
# def teacher_admin_route(
#     current_user: TeacherOrAdminUser
# ):
#     user, role = current_user
#     return {"message": f"Access granted as {role}", "user": user.username}
