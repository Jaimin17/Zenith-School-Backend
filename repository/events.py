import uuid
from datetime import date, time
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select, or_, and_
from datetime import datetime
from core.config import settings
from models import Event, Class, Student
from schemas import EventSave, EventUpdate


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


def getAllEventsByDate(session: Session, searchDate: date):
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


def getAllEventsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .where(Event.is_delete == False)
    )

    query = query.order_by(Event.start_time.desc())

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()
    return events


def getAllEventsByTeacherAndIsDeleteFalse(teacherId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Event)
        .join(Class, onclause=(Event.class_id == Class.id), isouter=True)
        .where(
            Event.is_delete == False,
            (Class.supervisor_id == teacherId) | (Event.class_id == None)
        )
    )

    query = query.order_by(Event.start_time.desc())

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()
    return events


def getAllEventsByStudentAndIsDeleteFalse(studentId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id), isouter=True)
        .join(Student, onclause=(Class.id == Student.class_id))
        .where(
            Event.is_delete == False,
            (Student.id == studentId) | (Event.class_id == None)
        )
    )

    query = query.order_by(Event.start_time.desc())

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()
    return events


def getAllEventsByParentAndIsDeleteFalse(parentId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id))
        .join(Student, onclause=(Class.id == Student.class_id))
        .where(
            Event.is_delete == False,
            (Student.parent_id == parentId) | (Event.class_id == None)
        )
    )

    query = query.order_by(Event.start_time.desc())

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()
    return events


def eventSave(event: EventSave, session: Session):
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

    new_event = Event(
        title=title,
        description=description,
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


def eventUpdate(event: EventUpdate, session: Session):
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

    current_event.start_time = event.start_time
    current_event.end_time = event.end_time
    current_event.description = description

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
