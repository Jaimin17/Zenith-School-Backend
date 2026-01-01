import uuid
from datetime import date
from typing import Optional

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.FileStorage import process_and_save_pdf, cleanup_pdf
from core.config import settings
from models import Announcement, Class, Student
from schemas import AnnouncementSave, AnnouncementUpdate


def addSearchOption(query: Select, search: str):
    if search is not None:
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

    query = query.order_by(Announcement.announcement_date.desc())

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

    query = query.order_by(Announcement.announcement_date.desc())

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

    query = query.order_by(Announcement.announcement_date.desc())

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

    query = query.order_by(Announcement.announcement_date.desc())

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements


async def announcementSave(announcement: AnnouncementSave, pdf: Optional[UploadFile], userId: uuid.UUID, role: str,
                           session: Session):
    title = announcement.title.strip()
    description = announcement.description.strip()
    announcement_date = announcement.announcement_date

    related_class: Optional[Class] = None
    if announcement.class_id:
        class_query = select(Class).where(
            Class.id == announcement.class_id,
            Class.is_delete == False
        )
        related_class = session.exec(class_query).first()

        if not related_class:
            raise HTTPException(
                status_code=404,
                detail=f"No class found with ID: {announcement.class_id}"
            )

        # Check teacher authorization - teacher can only create announcements for their supervised class
        if role == "teacher":
            if related_class.supervisor_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to create announcements for this class. You can only create announcements for classes you supervise."
                )

    search_duplicate_query = (
        select(Announcement)
        .where(
            Announcement.title.ilike(f"%{title}%"),
            Announcement.announcement_date == announcement_date,
            Announcement.is_delete == False
        )
    )

    if announcement.class_id:
        search_duplicate_query = search_duplicate_query.where(
            Announcement.class_id == announcement.class_id
        )

    duplicate_announcement: Optional[Announcement] = session.exec(search_duplicate_query).first()

    if duplicate_announcement:
        scope = f"class '{related_class.name}'" if related_class else "all classes"
        raise HTTPException(
            status_code=409,
            detail=f"An announcement with the title '{title}' already exists for {announcement_date} in {scope}."
        )

    pdf_filename: Optional[str] = None
    if pdf and pdf.filename:
        try:
            pdf_filename = await process_and_save_pdf(pdf, "announcements", title)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

    new_announcement = Announcement(
        title=title,
        description=description,
        announcement_date=announcement_date,
        class_id=announcement.class_id,
        attachment=pdf_filename,
        is_delete=False
    )

    session.add(new_announcement)

    try:
        session.flush()
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if pdf_filename:
            pdf_path = settings.UPLOAD_DIR_PDF / "announcements" / pdf_filename
            cleanup_pdf(pdf_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_announcement)

    if announcement.class_id and related_class:
        audience = f"class '{related_class.name}'"
    else:
        audience = "all classes"

    return {
        "id": str(new_announcement.id),
        "message": f"Announcement created successfully for {audience}"
    }


async def announcementUpdate(announcement: AnnouncementUpdate, pdf: Optional[UploadFile], userId: uuid.UUID, role: str,
                             session: Session):
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
                detail=f"No class found with ID: {announcement.class_id}"
            )

        if role == "teacher":
            if selected_class.supervisor_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to update announcements for this class. You can only create announcements for classes you supervise."
                )

        class_id = selected_class.id

    old_pdf_filename = current_announcement.attachment
    if pdf is not None:
        try:
            pdf_filename = await process_and_save_pdf(pdf, "announcements", title)
            current_announcement.attachment = pdf_filename

            # Clean up old PDF after successful upload
            if old_pdf_filename:
                old_pdf_path = settings.UPLOAD_DIR_PDF / "announcements" / old_pdf_filename
                cleanup_pdf(old_pdf_path)

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

    current_announcement.title = title
    current_announcement.description = description
    current_announcement.announcement_date = announcement_date
    current_announcement.class_id = class_id

    session.add(current_announcement)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if pdf is not None and current_announcement.attachment != old_pdf_filename:
            new_pdf_path = settings.UPLOAD_DIR_PDF / "announcements" / current_announcement.attachment
            cleanup_pdf(new_pdf_path)
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
