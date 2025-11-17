from datetime import timedelta
from enum import Enum
from typing import Any, Union

from deps import CurrentUser, require_roles, UserRole, AdminUser, TeacherOrAdminUser
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from core.database import SessionDep
from core.security import verify_password, create_access_token
from models import User, Admin, Teacher, Parent, Student
from schemas import Token, UserPublic

router = APIRouter(
    prefix="/login"
)


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



@router.post("/access-token", response_model=Token)
def login_access_token(session: SessionDep, request: OAuth2PasswordRequestForm = Depends()):
    user_data = get_user_by_username(request.username, session)
    if not user_data:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    db_user, role = user_data

    # Note: You'll need to add password field to your models
    if not verify_password(request.password, db_user.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Check if user is soft-deleted (except Admin which doesn't have is_delete)
    if role != "admin" and hasattr(db_user, 'is_delete') and db_user.is_delete:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Create token with role information
    access_token = create_access_token(subject={
        "sub": db_user.username,
        "role": role,
        "user_id": str(db_user.id) # Include user ID for easier lookups
    })

    return Token(access_token=access_token, token_type="bearer")

@router.post("/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    return current_user

# Example usage in routes:
@router.get("/admin-only")
def admin_only_route(
    current_user: AdminUser
):
    user, role = current_user
    return {"message": "Admin access granted", "user": user.username}


@router.get("/teacher-or-admin")
def teacher_admin_route(
    current_user: TeacherOrAdminUser
):
    user, role = current_user
    return {"message": f"Access granted as {role}", "user": user.username}