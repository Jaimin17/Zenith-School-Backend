from enum import Enum
from typing import Annotated, Union

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.exc import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import select
from starlette import status

from core import security
from core.config import settings
from core.database import SessionDep
from models import User, Admin, Parent, Teacher, Student
from schemas import UserPublic, TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/access-token"
)


class UserRole(str, Enum):
    ADMIN = "admin"
    PARENT = "parent"
    TEACHER = "teacher"
    STUDENT = "student"


TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> tuple[Union[Admin, Parent, Teacher, Student], str]:
    """
        Returns tuple of (user_object, role)
    """

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    # Fetch user based on role
    user = None
    role = token_data.role

    if role == "admin":
        user = session.exec(select(Admin).where(Admin.id == token_data.user_id)).first()
    elif role == "parent":
        user = session.exec(select(Parent).where(Parent.id == token_data.user_id)).first()
    elif role == "teacher":
        user = session.exec(select(Teacher).where(Teacher.id == token_data.user_id)).first()
    elif role == "student":
        user = session.exec(select(Student).where(Student.id == token_data.user_id)).first()

    # user = session.query(User).filter_by(username=token_data.sub).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user is soft-deleted (except Admin)
    if role != "admin" and hasattr(user, 'is_delete') and user.is_delete:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user, role


CurrentUser = Annotated[tuple[Union[Admin, Parent, Teacher, Student], str], Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole):
    """
        Dependency to check if current user has required role.
        Usage: current_user: CurrentUser = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER))
    """

    def role_checker(current_user: CurrentUser):
        user, role = current_user
        if role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join([r.value for r in allowed_roles])}"
            )
        return current_user

    return role_checker


# Pre-defined type aliases for common role combinations
AdminUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.ADMIN))
]

StudentOrTeacherOrAdminUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN))
]

TeacherOrAdminUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER))
]

ParentOrTeacherOrAdminUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER, UserRole.PARENT))
]

ParentUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.PARENT))
]

StudentUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.STUDENT))
]

StudentOrParentUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.STUDENT, UserRole.PARENT))
]

StudentOrParentOrAdminUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.STUDENT, UserRole.PARENT, UserRole.ADMIN))
]

AllUser = Annotated[
    tuple[Union[Admin, Parent, Teacher, Student], str],
    Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER, UserRole.STUDENT, UserRole.PARENT))
]
