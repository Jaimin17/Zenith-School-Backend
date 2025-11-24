import uuid

from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Student, Teacher, Exam, Assignment, Result, Lesson, Class


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (
                func.lower(Student.username).like(search_pattern) |
                func.lower(Student.first_name).like(search_pattern) |
                func.lower(Student.last_name).like(search_pattern)
            ) |
            (
                func.lower(Teacher.username).like(search_pattern) |
                func.lower(Teacher.first_name).like(search_pattern) |
                func.lower(Teacher.last_name).like(search_pattern)
            ) |
            (
                func.lower(Exam.title).like(search_pattern)
            ) |
            (
                func.lower(Assignment.title).like(search_pattern)
            )
        )

    return query

def getAllResultsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(Result.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()
    return all_results


def getAllResultsByTeacherIsDeleteFalse(teacherId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Teacher.id == teacherId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()
    return all_results


def getAllResultsOfClassIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Lesson.class_id == classId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()
    return all_results

def getAllResultsOfStudentIsDeleteFalse(studentId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Result.student_id == studentId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()
    return all_results

def getAllResultsOfParentIsDeleteFalse(parentId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Student.parent_id == parentId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()
    return all_results