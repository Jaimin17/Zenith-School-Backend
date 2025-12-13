import uuid
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select, or_

from core.config import settings
from models import Parent, Student
from schemas import ParentSave, ParentUpdate


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Parent.username).like(search_pattern)) |
            (func.lower(Parent.first_name).like(search_pattern)) |
            (func.lower(Parent.last_name).like(search_pattern))
        )

    return query


def countParent(session: Session):
    return session.exec(
        select(func.count()).select_from(Parent).where(Parent.is_delete == False)
    ).first()


def getAllParentIsDeleteFalse(session: Session, search: str = None, page: int = 1):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Parent)
        .where(Parent.is_delete == False)
    )

    query = query.order_by(func.lower(Parent.username))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_parents = session.exec(query).all()
    return active_parents


def parentSave(parent: ParentSave, session: Session):
    username = parent.username.strip().lower()
    first_name = parent.first_name.strip()
    last_name = parent.last_name.strip()
    email = parent.email.strip().lower()
    phone = parent.phone.strip()
    address = parent.address.strip()

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must be at least 3 characters long."
        )

    if len(first_name) < 1 or len(last_name) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name and last name are required."
        )

    if len(phone) != 10 or not phone.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Phone number must be exactly 10 digits."
        )

    if len(address) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address must be at least 10 characters long."
        )

    duplicate_query = (
        select(Parent)
        .where(
            or_(
                func.lower(func.trim(Parent.username)) == username,
                func.lower(func.trim(Parent.email)) == email,
                func.trim(Parent.phone) == phone
            ),
            Parent.is_delete == False
        )
    )
    existing_parent = session.exec(duplicate_query).first()

    if existing_parent:
        if existing_parent.username.lower() == username:
            detail = "Username already exists."
        elif existing_parent.email.lower() == email:
            detail = "Email already exists."
        else:
            detail = "Phone number already exists."

        raise HTTPException(
            status_code=400,
            detail=detail
        )

    new_parent = Parent(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        address=address,
        password="user@123",
        is_delete=False
    )

    session.add(new_parent)

    try:
        session.flush()
        session.commit()
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        if "username" in error_msg.lower():
            detail = "Username already exists."
        elif "email" in error_msg.lower():
            detail = "Email already exists."
        elif "phone" in error_msg.lower():
            detail = "Phone number already exists."
        else:
            detail = "Database integrity error. Please check your data."

        raise HTTPException(status_code=400, detail=detail)

    session.refresh(new_parent)

    return {
        "id": str(new_parent.id),
        "message": "Parent created successfully"
    }


def parentUpdate(parent: ParentUpdate, session: Session):
    findParentQuery = (
        select(Parent)
        .where(Parent.id == parent.id, Parent.is_delete == False)
    )

    current_parent: Optional[Parent] = session.exec(findParentQuery).first()

    if not current_parent:
        raise HTTPException(
            status_code=404,
            detail="Parent not found with provided ID."
        )

    username = parent.username.strip().lower()
    first_name = parent.first_name.strip()
    last_name = parent.last_name.strip()
    email = parent.email.strip().lower()
    phone = parent.phone.strip()
    address = parent.address.strip()

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must be at least 3 characters long."
        )

    if len(first_name) < 1 or len(last_name) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name and last name are required."
        )

    if len(phone) != 10 or not phone.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Phone number must be exactly 10 digits."
        )

    if len(address) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address must be at least 10 characters long."
        )

    duplicate_query = (
        select(Parent)
        .where(
            or_(
                func.lower(func.trim(Parent.username)) == username,
                func.lower(func.trim(Parent.email)) == email,
                func.trim(Parent.phone) == phone
            ),
            Parent.is_delete == False,
            Parent.id != parent.id
        )
    )
    existing_parent = session.exec(duplicate_query).first()

    if existing_parent:
        if existing_parent.username.lower() == username:
            detail = "Username already exists."
        elif existing_parent.email.lower() == email:
            detail = "Email already exists."
        else:
            detail = "Phone number already exists."

        raise HTTPException(
            status_code=400,
            detail=detail
        )

    current_parent.username = username
    current_parent.first_name = first_name
    current_parent.last_name = last_name
    current_parent.email = email
    current_parent.phone = phone
    current_parent.address = address

    session.add(current_parent)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Unique constraint violated (username/email/phone).")

    session.refresh(current_parent)

    return {
        "id": str(current_parent.id),
        "message": "Parent updated successfully"
    }


def parentSoftDelete(id: uuid.UUID, session: Session):
    findParent = (
        select(Parent)
        .where(Parent.id == id, Parent.is_delete == False)
    )

    current_parent: Optional[Parent] = session.exec(findParent).first()

    if not current_parent:
        raise HTTPException(
            status_code=404,
            detail="Parent not found with provided ID."
        )

    findLinkedStudent = (
        select(Student)
        .where(Student.parent_id == id, Student.is_delete == False)
    )

    linkedStudent: Optional[Student] = session.exec(findLinkedStudent).first()

    if linkedStudent:
        raise HTTPException(
            status_code=400,
            detail="Can't delete. Student is linked with this parent."
        )

    current_parent.is_delete = True

    session.add(current_parent)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Error deleting parent and related records.")

    session.refresh(current_parent)

    return {
        "id": str(current_parent.id),
        "message": "Parent deleted successfully.",
    }
