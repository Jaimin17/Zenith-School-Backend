import uuid

from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Assignment, Lesson, Class, Student


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Assignment.title).like(search_pattern))
        )

    return query

def getAllAssignmentsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Assignment)
        .where(Assignment.is_delete == False)
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_exams = session.exec(query).unique().all()
    return all_exams

def getAllAssignmentsOfTeacherIsDeleteFalse(teacherId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Assignment)
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .where(
            Lesson.teacher_id == teacherId,
            Assignment.is_delete == False,
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()
    return all_assignments

def getAllAssignmentsOfParentIsDeleteFalse(parentId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Assignment)
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .join(Class, onclause=(Class.id == Lesson.class_id))
        .join(Student, onclause=(Student.class_id == Class.id))
        .where(
            Student.parent_id == parentId,
            Assignment.is_delete == False,
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()
    return all_assignments

def getAllAssignmentsOfClassIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Assignment)
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .where(
            Lesson.class_id == classId,
            Assignment.is_delete == False,
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()
    return all_assignments