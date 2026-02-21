from datetime import timedelta, date, datetime
from enum import Enum
from math import dist
from typing import Any, Union

from fastapi.params import Form
from jwt import PyJWTError
from core.config import settings
from core.security import get_password_hash
from deps import CurrentUser, UserRole, AdminUser, TeacherOrAdminUser, AllUser, TokenDep
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from core.database import SessionDep
from core.security import verify_password, create_access_token, create_refresh_token, decode_refresh_token, secureLogout
from models import User, Admin, Teacher, Parent, Student, BlacklistToken
from schemas import Token, UserPublic, RefreshTokenRequest, TokenWithUser, AdminResponse, ParentResponse, \
    TeacherResponse, StudentResponse
from core.FileStorage import process_and_save_image

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


@router.post("/changePassword", response_model=str)
def changeUserPassword(
        current_user: AllUser,
        session: SessionDep,
        old_password: str = Form(...),
        new_password: str = Form(...),
        confirm_password: str = Form(...)
):
    db_user, role = current_user

    # 1. Check current password
    if not verify_password(old_password, db_user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # 2. Check new password and confirmation match
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")

    # 3. Optionally, check new password is different from current
    if verify_password(new_password, db_user.password):
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    # 4. Update password for the user based on role
    db_user.password = get_password_hash(new_password)
    session.add(db_user)
    session.commit()

    return "Password changed successfully."


@router.put("/updateProfile", response_model=dict)
def update_profile(
        current_user: AllUser,
        session: SessionDep,
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        address: str = Form(...)
):
    db_user, role = current_user

    # Validate email
    if not settings.EMAIL_RE.match(email.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format."
        )

    # Validate phone
    if not settings.PHONE_RE.match(phone.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid Indian phone number. Must be 10 digits starting with 6-9."
    )

    if first_name and len(first_name.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="First name should be at least 2 characters long."
        )
    
    if last_name and len(last_name.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Last name should be at least 2 characters long."
        )
    
    if address and len(address.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Address should be at least 5 characters long."
        )

    # Update basic info
    db_user.first_name = first_name
    db_user.last_name = last_name
    db_user.email = email
    db_user.phone = phone
    db_user.address = address

    session.add(db_user)
    session.commit()

    return {"message": "Profile updated successfully", "user": format_user_response(db_user, role)}



@router.post("/updateProfilePicture", response_model=str)
async def update_profile_picture(
        current_user: AllUser,
        session: SessionDep,
        file: UploadFile = Form(...)
):
    db_user, role = current_user

    # Validate file type (e.g., only allow JPEG and PNG)
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only JPEG and PNG are allowed."
        )

    image_filename = None

    if role == UserRole.STUDENT and file.filename:
        try:
            image_filename = await process_and_save_image(file, "students", db_user.username)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    if role == UserRole.TEACHER and file.filename:
        try:
            image_filename = await process_and_save_image(file, "teachers", db_user.username)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    # Update user's profile picture URL
    db_user.img = image_filename
    session.add(db_user)
    session.commit()

    return "Profile picture updated successfully."

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
