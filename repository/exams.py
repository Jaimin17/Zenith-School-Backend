import uuid

from dns.e164 import query
from sqlalchemy import Select, func, false
from sqlmodel import select, Session

from core.config import settings
from models import Exam, Lesson, Student, Class


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

def getAllExamsOfParentIsDeleteFalse(parentId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Exam)
        .join(Lesson, onclause=(Exam.lesson_id == Lesson.id))
        .join(Class, onclause=(Class.id == Lesson.class_id))
        .join(Student, onclause=(Student.class_id == Class.id))
        .where(
            Student.parent_id == parentId,
            Exam.is_delete == False
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_exams = session.exec(query).unique().all()
    return all_exams
