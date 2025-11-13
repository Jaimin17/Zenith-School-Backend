import uuid

from sqlalchemy import Select, func
from sqlmodel import select, Session

from core.config import settings
from models import Exam, Lesson

def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Exam.title).like(search_pattern))
        )

    return query

def getAllExamsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Exam)
        .where(Exam.is_delete == False)
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_exams = session.exec(query).unique().all()
    return all_exams

def getAllExamsOfTeacherIsDeleteFalse(teacherId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Exam)
        .join(Lesson, onclause=(Exam.lesson_id == Lesson.id))
        .where(
            Lesson.teacher_id == teacherId,
            Exam.is_delete == False,
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_exams = session.exec(query).unique().all()
    return all_exams

def getAllExamsOfClassIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Exam)
        .join(Lesson, onclause=(Exam.lesson_id == Lesson.id))
        .where(
            Lesson.class_id == classId,
            Exam.is_delete == False,
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_exams = session.exec(query).unique().all()
    return all_exams