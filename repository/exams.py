import uuid
from datetime import datetime, timezone
from typing import Optional, List

from dns.e164 import query
from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func, false
from sqlmodel import select, Session, or_, and_

from core.config import settings
from models import Exam, Lesson, Student, Class, Result
from schemas import ExamSave, ExamUpdate


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


def examSave(exam: ExamSave, userId: uuid.UUID, role: str, session: Session):
    lesson_query = (
        select(Lesson)
        .where(Lesson.id == exam.lesson_id, Lesson.is_delete == False)
    )
    lesson: Optional[Lesson] = session.exec(lesson_query).first()

    if not lesson:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found with the provided ID."
        )

    if role.lower() == "teacher":
        if lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="Teachers can only create exams for their own lessons."
            )

    duplicate_title_query = (
        select(Exam)
        .where(
            Exam.lesson_id == exam.lesson_id,
            Exam.title.ilike(f"%{exam.title.strip()}%"),
            Exam.is_delete == False
        )
    )
    existing_title = session.exec(duplicate_title_query).first()

    if existing_title:
        raise HTTPException(
            status_code=400,
            detail=f"An exam with similar title already exists for this lesson."
        )

    if lesson.class_id:
        # Get all lessons for the same class
        class_lessons_query = (
            select(Lesson)
            .where(
                Lesson.class_id == lesson.class_id,
                Lesson.is_delete == False
            )
        )
        class_lessons = session.exec(class_lessons_query).all()
        class_lesson_ids = [l.id for l in class_lessons]

        if class_lesson_ids:
            # Check for overlapping exams in any lesson of the same class
            time_conflict_query = (
                select(Exam)
                .where(
                    Exam.lesson_id.in_(class_lesson_ids),
                    Exam.is_delete == False,
                    or_(
                        # New exam starts during existing exam
                        and_(
                            Exam.start_time <= exam.start_time,
                            Exam.end_time > exam.start_time
                        ),
                        # New exam ends during existing exam
                        and_(
                            Exam.start_time < exam.end_time,
                            Exam.end_time >= exam.end_time
                        ),
                        # New exam completely contains existing exam
                        and_(
                            Exam.start_time >= exam.start_time,
                            Exam.end_time <= exam.end_time
                        )
                    )
                )
            )
            conflicting_exam = session.exec(time_conflict_query).first()

            if conflicting_exam:
                raise HTTPException(
                    status_code=400,
                    detail=f"Time conflict: Another exam '{conflicting_exam.title}' is scheduled for this class at the same time."
                )

    new_exam = Exam(
        title=exam.title.strip(),
        start_time=exam.start_time,
        end_time=exam.end_time,
        lesson_id=exam.lesson_id,
        is_delete=False
    )

    session.add(new_exam)

    try:
        session.flush()
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_exam)

    return {
        "id": str(new_exam.id),
        "message": "Exam created successfully"
    }


def examUpdate(exam: ExamUpdate, userId: uuid.UUID, role: str, session: Session):
    find_exam_query = (
        select(Exam)
        .where(Exam.id == exam.id, Exam.is_delete == False)
    )
    current_exam: Optional[Exam] = session.exec(find_exam_query).first()

    if not current_exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found with the provided ID."
        )

    current_lesson_query = (
        select(Lesson)
        .where(Lesson.id == current_exam.lesson_id, Lesson.is_delete == False)
    )
    current_lesson: Optional[Lesson] = session.exec(current_lesson_query).first()

    if not current_lesson:
        raise HTTPException(
            status_code=404,
            detail="Associated lesson not found or has been deleted."
        )

    if role.lower() == "teacher":
        if current_lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="Teachers can only update exams for their own lessons."
            )

    duplicate_title_query = (
        select(Exam)
        .where(
            Exam.lesson_id == current_exam.lesson_id,
            Exam.id != exam.id,
            Exam.title.ilike(f"%{exam.title.strip()}%"),
            Exam.is_delete == False
        )
    )
    existing_title = session.exec(duplicate_title_query).first()

    if existing_title:
        raise HTTPException(
            status_code=400,
            detail=f"An exam with similar title already exists for this lesson."
        )

    current_exam.title = exam.title.strip()

    new_lesson = None
    if exam.lesson_id is not None and exam.lesson_id != current_exam.lesson_id:
        # Verify new lesson exists
        new_lesson_query = (
            select(Lesson)
            .where(Lesson.id == exam.lesson_id, Lesson.is_delete == False)
        )
        new_lesson = session.exec(new_lesson_query).first()

        if not new_lesson:
            raise HTTPException(
                status_code=404,
                detail="New lesson not found with the provided ID."
            )

        # Role-based validation for new lesson
        if role.lower() == "teacher":
            if new_lesson.teacher_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="Teachers can only assign exams to their own lessons."
                )

        current_exam.lesson_id = exam.lesson_id

    start_time = exam.start_time
    end_time = exam.end_time

    lesson_for_conflict_check = new_lesson if new_lesson else current_lesson

    if lesson_for_conflict_check.class_id:
        # Get all lessons for the same class
        class_lessons_query = (
            select(Lesson)
            .where(
                Lesson.class_id == lesson_for_conflict_check.class_id,
                Lesson.is_delete == False
            )
        )
        class_lessons = session.exec(class_lessons_query).all()
        class_lesson_ids = [l.id for l in class_lessons]

        if class_lesson_ids:
            # Check for overlapping exams (excluding current exam)
            time_conflict_query = (
                select(Exam)
                .where(
                    Exam.lesson_id.in_(class_lesson_ids),
                    Exam.id != exam.id,  # Exclude current exam
                    Exam.is_delete == False,
                    or_(
                        # New exam starts during existing exam
                        and_(
                            Exam.start_time <= start_time,
                            Exam.end_time > start_time
                        ),
                        # New exam ends during existing exam
                        and_(
                            Exam.start_time < end_time,
                            Exam.end_time >= end_time
                        ),
                        # New exam completely contains existing exam
                        and_(
                            Exam.start_time >= start_time,
                            Exam.end_time <= end_time
                        )
                    )
                )
            )
            conflicting_exam = session.exec(time_conflict_query).first()

            if conflicting_exam:
                raise HTTPException(
                    status_code=400,
                    detail=f"Time conflict: Another exam '{conflicting_exam.title}' is scheduled for this class at the same time."
                )

    if exam.start_time is not None:
        current_exam.start_time = exam.start_time
    if exam.end_time is not None:
        current_exam.end_time = exam.end_time

    session.add(current_exam)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_exam)

    return {
        "id": str(current_exam.id),
        "message": "Exam updated successfully"
    }


def examSoftDelete(id: uuid.UUID, session: Session):
    current_exam_query = (
        select(Exam)
        .where(Exam.id == id, Exam.is_delete == False)
    )

    current_exam: Optional[Exam] = session.exec(current_exam_query).first()

    if not current_exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found with provided id."
        )

    result_query = (
        select(Result)
        .where(Result.exam_id == id, Result.is_delete == False)
    )
    results: List[Result] = session.exec(result_query).all()

    affected_results = 0
    for result in results:
        result.is_delete = True
        session.add(result)
        affected_results += 1

    current_exam.is_delete = True
    session.add(current_exam)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error deleting exam and related records."
        )

    session.refresh(current_exam)

    return {
        "id": str(current_exam.id),
        "message": "Exam soft-deleted successfully.",
        "result_affected": affected_results
    }
