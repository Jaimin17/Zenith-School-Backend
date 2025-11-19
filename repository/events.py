from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Event, Class, Student


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

def getAllEventsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id))
        .where(Event.is_delete == False)
    )

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

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()
    return events