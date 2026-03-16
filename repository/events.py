import uuid
from datetime import date, time, timezone
from typing import Optional

from PIL.ImageChops import offset
from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select, or_, and_
from datetime import datetime
from fastapi import UploadFile
from core.config import settings
from core.FileStorage import process_and_save_image, cleanup_image
from models import Event, Class, Student, StudentClassHistory, AcademicYear
from schemas import EventSave, EventUpdate, PaginatedEventResponse

EVENT_IMAGE_FOLDER = "events"


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (
                    func.lower(Event.title).like(search_pattern) |
                    func.lower(Event.description).like(search_pattern)
            ) | (
                func.lower(Class.name).like(search_pattern)
            )
        )

    return query


def getAllEventsByDate(session: Session, searchDate: date, user, role: str):
    day_start = datetime.combine(searchDate, time.min)
    day_end = datetime.combine(searchDate, time.max)
    print(f"From {day_start} to {day_end}")
    query = (
        select(Event)
        .where(
            Event.is_delete == False,
            Event.start_time <= day_end,
            Event.end_time >= day_start
        )
    )

    if role == "teacher":
        # Teachers see events for their classes
        query = query.join(Class, Event.class_id == Class.id).where(
            Class.supervisor_id == user.id,
            Class.is_delete == False
        )
    elif role == "student":
        # Students see events for their class
        query = query.join(Class, Event.class_id == Class.id).join(
            Student, Class.id == Student.class_id
        ).where(
            Student.id == user.id,
            Student.is_delete == False,
            Class.is_delete == False
        )
    elif role == "parent":
        # Parents see events for their children's classes
        query = query.join(Class, Event.class_id == Class.id).join(
            Student, Class.id == Student.class_id
        ).where(
            Student.parent_id == user.id,
            Student.is_delete == False,
            Class.is_delete == False
        )

    query = query.order_by(Event.start_time)

    events = session.exec(query).unique().all()
    return events


def getEventById(session: Session, eventId: uuid.UUID):
    query = (
        select(Event)
        .options(
            selectinload(Event.related_class).selectinload(Class.students),
        )
        .where(
            Event.id == eventId,
            Event.is_delete == False
        )
    )

    event_detail: Optional[Event] = session.exec(query).first()
    return event_detail


def getAllPublicEventsAndIsDeleteFalse(session: Session, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Count query
    count_query = (
        select(func.count(Event.id.distinct()))
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .where(Event.is_delete == False)
    )
    total_count = session.exec(count_query).one()

    # Data query
    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .where(Event.is_delete == False)
    )
    query = query.order_by(Event.start_time.desc())
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedEventResponse(
        data=events,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllEventsIsDeleteFalse(session: Session, search: str, page: int, from_date: date = None, to_date: date = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    where_cond = [Event.is_delete == False]
    if from_date:
        where_cond.append(func.date(Event.start_time) >= from_date)
    if to_date:
        where_cond.append(func.date(Event.start_time) <= to_date)

    # Count query
    count_query = (
        select(func.count(Event.id.distinct()))
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .where(*where_cond)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Data query
    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .where(*where_cond)
    )
    query = query.order_by(Event.start_time.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedEventResponse(
        data=events,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllEventsByTeacherAndIsDeleteFalse(teacherId, session, search, page, from_date: date = None,
                                          to_date: date = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    base_cond = [
        Event.is_delete == False,
        (Class.supervisor_id == teacherId) | (Event.class_id == None)
    ]
    if from_date:
        base_cond.append(func.date(Event.start_time) >= from_date)
    if to_date:
        base_cond.append(func.date(Event.start_time) <= to_date)

    # Count query
    count_query = (
        select(func.count(Event.id.distinct()))
        .join(Class, onclause=(Event.class_id == Class.id), isouter=True)
        .where(*base_cond)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Data query
    query = (
        select(Event)
        .join(Class, onclause=(Event.class_id == Class.id), isouter=True)
        .where(*base_cond)
    )
    query = query.order_by(Event.start_time.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedEventResponse(
        data=events,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllEventsByStudentAndIsDeleteFalse(studentId, session, search, page, from_date: date = None,
                                          to_date: date = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    base_cond = [
        Event.is_delete == False,
        or_(
            Student.id == studentId,
            Event.class_id == None
        )
    ]
    if from_date:
        base_cond.append(func.date(Event.start_time) >= from_date)
    if to_date:
        base_cond.append(func.date(Event.start_time) <= to_date)

    current_class_query = (
        select(StudentClassHistory)
        .join(AcademicYear, onclause=(AcademicYear.id == StudentClassHistory.academic_year_id))
        .where(
            StudentClassHistory.student_id == studentId,
            AcademicYear.start_date == from_date,
            AcademicYear.is_delete == False,
        )
    )

    current_class_detail: Optional[StudentClassHistory] = session.exec(current_class_query).first()

    # Count query
    count_query = (
        select(func.count(Event.id.distinct()))
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .join(Student, onclause=(Class.id == current_class_detail.class_id))
        .where(*base_cond)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Data query
    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .join(Student, onclause=(Class.id == current_class_detail.class_id))
        .where(*base_cond)
    )
    query = query.order_by(Event.start_time.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedEventResponse(
        data=events,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllEventsByParentAndIsDeleteFalse(parentId, session, search, page, from_date: date = None, to_date: date = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    base_cond = [
        Event.is_delete == False,
        (Student.parent_id == parentId) | (Event.class_id == None)
    ]
    if from_date:
        base_cond.append(func.date(Event.start_time) >= from_date)
    if to_date:
        base_cond.append(func.date(Event.start_time) <= to_date)

    current_class_query = (
        select(StudentClassHistory)
        .join(AcademicYear, onclause=(AcademicYear.id == StudentClassHistory.academic_year_id))
        .where(
            AcademicYear.start_date == from_date,
            AcademicYear.is_delete == False,
        )
    )

    current_class_detail: Optional[StudentClassHistory] = session.exec(current_class_query).first()

    # Count query
    count_query = (
        select(func.count(Event.id.distinct()))
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .join(Student, onclause=(Class.id == current_class_detail.class_id))
        .where(*base_cond)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Data query
    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .join(Student, onclause=(Class.id == current_class_detail.class_id))
        .where(*base_cond)
    )
    query = query.order_by(Event.start_time.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedEventResponse(
        data=events,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


async def eventSave(event: EventSave, images: list[UploadFile], session: Session):
    title = event.title.strip()
    description = event.description.strip()

    search_duplicate_query = (
        select(Event)
        .where(
            Event.title.ilike(f"%{title}%"),
            Event.is_delete == False
        )
    )
    duplicate_event = session.exec(search_duplicate_query).first()

    if duplicate_event:
        raise HTTPException(
            status_code=400,
            detail="An event with similar title already exists."
        )

    class_id = None
    if event.class_id is not None:
        class_query = (
            select(Class)
            .where(Class.id == event.class_id, Class.is_delete == False)
        )
        selected_class = session.exec(class_query).first()

        if not selected_class:
            raise HTTPException(
                status_code=404,
                detail="Class not found or has been deleted."
            )

        class_id = selected_class.id

        time_conflict_query = (
            select(Event)
            .where(
                or_(
                    Event.class_id == class_id,
                    Event.class_id == None
                ),
                Event.is_delete == False,
                or_(
                    and_(
                        Event.start_time <= event.start_time,
                        Event.end_time > event.start_time
                    ),
                    and_(
                        Event.start_time < event.end_time,
                        Event.end_time >= event.end_time
                    ),
                    and_(
                        Event.start_time >= event.start_time,
                        Event.end_time <= event.end_time
                    )
                )
            )
        )
        conflicting_event = session.exec(time_conflict_query).first()

        if conflicting_event:
            raise HTTPException(
                status_code=400,
                detail=f"Time conflict: Another event '{conflicting_event.title}' is scheduled for this class at the same time."
            )

    saved_filenames: list[str] = []
    try:
        for image in images:
            filename = await process_and_save_image(image, EVENT_IMAGE_FOLDER, title)
            saved_filenames.append(filename)
    except ValueError as e:
        for fname in saved_filenames:
            cleanup_image(settings.UPLOAD_DIR_DP / EVENT_IMAGE_FOLDER / fname)
        raise HTTPException(status_code=400, detail=str(e))

    new_event = Event(
        title=title,
        description=description,
        img=str(saved_filenames),
        start_time=event.start_time,
        end_time=event.end_time,
        class_id=class_id,
        is_delete=False
    )

    session.add(new_event)

    try:
        session.flush()
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_event)

    return {
        "id": str(new_event.id),
        "message": "Event created successfully"
    }


async def eventUpdate(event: EventUpdate, images: list[UploadFile], session: Session):
    title = event.title.strip()
    description = event.description.strip()

    current_event_query = (
        select(Event)
        .where(
            Event.id == event.id,
            Event.is_delete == False
        )
    )

    current_event: Optional[Event] = session.exec(current_event_query).first()

    if not current_event:
        raise HTTPException(
            status_code=404,
            detail="Event not found with provided ID."
        )

    if current_event.title != title:
        search_duplicate_query = (
            select(Event)
            .where(
                Event.id != event.id,
                Event.title.ilike(f"%{title}%"),
                Event.is_delete == False
            )
        )
        duplicate_event = session.exec(search_duplicate_query).first()

        if duplicate_event:
            raise HTTPException(
                status_code=400,
                detail="An event with similar title already exists."
            )

        current_event.title = title

    if event.class_id is not None:
        class_query = (
            select(Class)
            .where(Class.id == event.class_id, Class.is_delete == False)
        )
        selected_class = session.exec(class_query).first()

        if not selected_class:
            raise HTTPException(
                status_code=404,
                detail="Class not found or has been deleted."
            )

        # Check for time conflicts (exclude current event)
        time_conflict_query = (
            select(Event)
            .where(
                Event.id != event.id,
                or_(
                    Event.class_id == event.class_id,
                    Event.class_id == None
                ),
                Event.is_delete == False,
                or_(
                    # New event starts during existing event
                    and_(
                        Event.start_time <= event.start_time,
                        Event.end_time > event.start_time
                    ),
                    # New event ends during existing event
                    and_(
                        Event.start_time < event.end_time,
                        Event.end_time >= event.end_time
                    ),
                    # New event completely contains existing event
                    and_(
                        Event.start_time >= event.start_time,
                        Event.end_time <= event.end_time
                    )
                )
            )
        )
        conflicting_event = session.exec(time_conflict_query).first()

        if conflicting_event:
            raise HTTPException(
                status_code=400,
                detail=f"Time conflict: Another event '{conflicting_event.title}' is scheduled for this class at the same time."
            )

        current_event.class_id = event.class_id
    else:
        current_event.class_id = None

    print("current_event: ", current_event)
    print("Updated event: ", event)

    current_start_aware = current_event.start_time.replace(
        tzinfo=timezone.utc) if current_event.start_time.tzinfo is None else current_event.start_time
    event_start_aware = event.start_time.replace(
        tzinfo=timezone.utc) if event.start_time.tzinfo is None else event.start_time

    if current_start_aware != event_start_aware and event_start_aware < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Event start time cannot be in the past."
        )

    current_event.start_time = event.start_time
    current_event.end_time = event.end_time
    current_event.description = description

    if images:
        saved_filenames: list[str] = []
        try:
            for image in images:
                filename = await process_and_save_image(image, EVENT_IMAGE_FOLDER, title)
                saved_filenames.append(filename)
        except ValueError as e:
            for fname in saved_filenames:
                cleanup_image(settings.UPLOAD_DIR_DP / EVENT_IMAGE_FOLDER / fname)
            raise HTTPException(status_code=400, detail=str(e))

        # Cleanup old images from disk before replacing
        if current_event.img:
            for old_filename in current_event.img:
                cleanup_image(settings.UPLOAD_DIR_DP / EVENT_IMAGE_FOLDER / old_filename)
        current_event.img = saved_filenames

    session.add(current_event)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_event)
    return {
        "id": str(current_event.id),
        "message": "Event updated successfully"
    }


def EventSoftDelete(id: uuid.UUID, session: Session):
    current_event_query = (
        select(Event)
        .where(
            Event.id == id,
            Event.is_delete == False
        )
    )

    current_event: Optional[Event] = session.exec(current_event_query).first()

    if not current_event:
        raise HTTPException(
            status_code=404,
            detail="Event not found or already deleted."
        )

    # Check if exam is in the future
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    event_start = current_event.start_time
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=timezone.utc)

    if event_start < now:
        raise HTTPException(
            status_code=400,
            detail="Only future events can be deleted. This event has already started or passed."
        )

    current_event.class_id = None
    current_event.is_delete = True

    try:
        session.add(current_event)
        session.commit()
        session.refresh(current_event)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while deleting event."
        )

    return {
        "id": str(current_event.id),
        "message": "Event deleted successfully"
    }
