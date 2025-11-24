import uuid

from sqlalchemy import func, Select
from sqlmodel import Session, select

from core.config import settings
from models import Teacher, Lesson


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Teacher.username).like(search_pattern)) |
            (func.lower(Teacher.first_name).like(search_pattern)) |
            (func.lower(Teacher.last_name).like(search_pattern))
        )

    return query

def countTeacher(session: Session):
    return session.exec(
        select(func.count()).select_from(Teacher).where(Teacher.is_delete == False)
    ).first()

def getAllTeachersIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Teacher)
        .where(Teacher.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_teachers = session.exec(query).all()
    return active_teachers

def getAllTeachersOfClassAndIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Teacher)
        .join(
            Lesson,
            onclause=(Lesson.teacher_id == Teacher.id)
        )
        .where(
            Lesson.class_id == classId,
            Teacher.is_delete == False,
        )
    )

    query = addSearchOption(query, search)


    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE).distinct()
    results = session.exec(query).all()
    return results