import uuid

from sqlmodel import Session, select
from sqlalchemy import func, Select
from core.config import settings
from models import Student, Teacher, Lesson, Class


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Student.username).like(search_pattern)) |
            (func.lower(Student.first_name).like(search_pattern)) |
            (func.lower(Student.last_name).like(search_pattern))
        )

    return query


def getAllStudentsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Student)
        .where(Student.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_students = session.exec(query).all()
    return active_students

def getAllStudentsOfTeacherAndIsDeleteFalse(session: Session, teacherId: uuid.UUID, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Student)
        .join(
            Class,
            onclause=(Class.id == Student.class_id)
        )
        .join(
            Lesson,
            onclause=(Lesson.class_id == Class.id)
        )
        .where(
            Lesson.teacher_id == teacherId,
            Student.is_delete == False,
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE).distinct()
    results = session.exec(query).all()
    return results