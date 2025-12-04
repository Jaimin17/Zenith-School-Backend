import uuid
from datetime import date
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Announcement, Class, Student
from schemas import AnnouncementSave, AnnouncementUpdate


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (
                    func.lower(Announcement.title).like(search_pattern) |
                    func.lower(Announcement.description).like(search_pattern)
            ) | (
                func.lower(Class.name).like(search_pattern)
            )
        )

    return query


def getAllAnnouncementsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .where(Announcement.is_delete == False)
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements


def getAllAnnouncementsByTeacherAndIsDeleteFalse(teacherId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .join(Class, onclause=(Announcement.class_id == Class.id), isouter=True)
        .where(
            Announcement.is_delete == False,
            (Class.supervisor_id == teacherId) | (Announcement.class_id == None)
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements


def getAllAnnouncementsByStudentAndIsDeleteFalse(studentId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .join(Class, onclause=(Class.id == Announcement.class_id), isouter=True)
        .join(Student, onclause=(Class.id == Student.class_id))
        .where(
            Announcement.is_delete == False,
            (Student.id == studentId) | (Announcement.class_id == None)
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements


def getAllAnnouncementsByParentAndIsDeleteFalse(parentId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .join(Class, onclause=(Class.id == Announcement.class_id))
        .join(Student, onclause=(Class.id == Student.class_id))
        .where(
            Announcement.is_delete == False,
            (Student.parent_id == parentId) | (Announcement.class_id == None)
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements


def announcementSave(announcement: AnnouncementSave, session: Session):
    title = announcement.title.strip()
    description = announcement.description.strip()

    if len(title) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if len(description) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    announcement_date = announcement.announcement_date if announcement.announcement_date else date.today()

    search_duplicate_query = (
        select(Announcement)
        .where(
            Announcement.title.ilike(f"%{title}%"),
            Announcement.announcement_date == announcement_date,
            Announcement.is_delete == False
        )
    )
    duplicate_announcement: Optional[Announcement] = session.exec(search_duplicate_query).first()

    if duplicate_announcement:
        raise HTTPException(
            status_code=400,
            detail=f"An announcement with similar title already exists for {announcement_date}."
        )

    class_id = None
    if announcement.class_id is not None:
        class_query = (
            select(Class)
            .where(Class.id == announcement.class_id, Class.is_delete == False)
        )
        selected_class = session.exec(class_query).first()

        if not selected_class:
            raise HTTPException(
                status_code=404,
                detail="Class not found or has been deleted."
            )

        class_id = selected_class.id

    new_announcement = Announcement(
        title=title,
        description=description,
        announcement_date=announcement_date,
        class_id=class_id,
        is_delete=False
    )

    session.add(new_announcement)

    try:
        session.flush()
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_announcement)

    return {
        "id": str(new_announcement.id),
        "message": "announcement created successfully"
    }


def announcementUpdate(announcement: AnnouncementUpdate, session: Session):
    announcement_query = (
        select(Announcement)
        .where(Announcement.id == announcement.id, Announcement.is_delete == False)
    )

    current_announcement: Optional[Announcement] = session.exec(announcement_query).first()
    print(f"This is announcement obj: {current_announcement}")
    if not current_announcement:
        raise HTTPException(
            status_code=404,
            detail="Announcement not found with provided ID."
        )

    title = announcement.title.strip()
    description = announcement.description.strip()

    if len(title) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if len(description) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    announcement_date = announcement.announcement_date if announcement.announcement_date else date.today()

    search_duplicate_query = (
        select(Announcement)
        .where(
            Announcement.title.ilike(f"%{title}%"),
            Announcement.announcement_date == announcement_date,
            Announcement.id != current_announcement.id,
            Announcement.is_delete == False
        )
    )
    duplicate_announcement: Optional[Announcement] = session.exec(search_duplicate_query).first()

    if duplicate_announcement:
        raise HTTPException(
            status_code=400,
            detail=f"An announcement with similar title already exists for {announcement_date}."
        )

    class_id = current_announcement.class_id
    if announcement.class_id is not None and announcement.class_id != current_announcement.class_id:
        class_query = (
            select(Class)
            .where(Class.id == announcement.class_id, Class.is_delete == False)
        )
        selected_class = session.exec(class_query).first()

        if not selected_class:
            raise HTTPException(
                status_code=404,
                detail="Class not found or has been deleted."
            )

        class_id = selected_class.id

    current_announcement.title = title
    current_announcement.description = description
    current_announcement.announcement_date = announcement_date
    current_announcement.class_id = class_id

    session.add(current_announcement)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_announcement)
    return {
        "id": str(current_announcement.id),
        "message": "Announcement updated successfully"
    }

def AnnouncementSoftDelete(id: uuid.UUID, session: Session):
    current_announcement_query = (
        select(Announcement)
        .where(
            Announcement.id == id,
            Announcement.is_delete == False
        )
    )

    current_announcement: Optional[Announcement] = session.exec(current_announcement_query).first()

    if not current_announcement:
        raise HTTPException(
            status_code=404,
            detail="Announcement not found or already deleted."
        )

    current_announcement.class_id = None
    current_announcement.is_delete = True

    try:
        session.add(current_announcement)
        session.commit()
        session.refresh(current_announcement)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while deleting announcement."
        )

    return {
        "id": str(current_announcement.id),
        "message": "Announcement deleted successfully"
    }