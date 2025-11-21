import uuid

from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Lesson, Teacher, Class, Student


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Lesson.name).like(search_pattern)) |
            (
                    func.lower(Teacher.username).like(search_pattern) |
                    func.lower(Teacher.first_name).like(search_pattern) |
                    func.lower(Teacher.last_name).like(search_pattern)
            ) |
            (
                    func.lower(Class.name).like(search_pattern)
            )
        )

    return query

def getAllLessonIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Lesson)
        .join(Teacher, onclause=(Lesson.teacher_id == Teacher.id))
        .join(Class, onclause=(Lesson.class_id == Class.id))
        .where(Lesson.is_delete == False)
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_lessons = session.exec(query).unique().all()
    return all_lessons

def getAllLessonOfTeacherIsDeleteFalse(teacherId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Lesson)
        .where(
            Lesson.teacher_id == teacherId,
            Lesson.is_delete == False
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_lessons = session.exec(query).unique().all()
    return all_lessons

def getAllLessonOfClassIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Lesson)
        .where(
            Lesson.class_id == classId,
            Lesson.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_lessons = session.exec(query).unique().all()
    return all_lessons

def getAllLessonOfParentIsDeleteFalse(parentId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Lesson)
        .join(Class, onclause=(Class.id == Lesson.class_id))
        .join(Student, onclause=(Student.class_id == Class.id))
        .where(
            Student.parent_id == parentId,
            Lesson.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_lessons = session.exec(query).unique().all()
    return all_lessons