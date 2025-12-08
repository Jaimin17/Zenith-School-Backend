import uuid
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select, or_, and_

from core.config import settings
from models import Lesson, Teacher, Class, Student, Subject, Exam, Assignment, Attendance
from schemas import LessonSave, LessonUpdate


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


def countAllLessonOfTeacher(teacherId: uuid.UUID, session: Session):
    query = (
        select(func.count())
        .select_from(Lesson)
        .where(Lesson.teacher_id == teacherId, Lesson.is_delete == False)
    )

    total_lessons = session.exec(query).one()
    return total_lessons


def countAllLessonOfStudent(studentId: uuid.UUID, session: Session):
    query = (
        select(func.count())
        .select_from(Lesson)
        .join(Class, onclause=(Class.id == Lesson.class_id))
        .join(Student, onclause=(Student.class_id == Class.id))
        .where(Student.id == studentId, Lesson.is_delete == False)
    )

    total_lessons = session.exec(query).one()
    return total_lessons


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


def lessonSave(lesson: LessonSave, session: Session):
    name = lesson.name.strip()

    if len(name) < 3:
        raise HTTPException(
            status_code=400,
            detail="Lesson name must be at least 3 characters long."
        )

    if lesson.start_time >= lesson.end_time:
        raise HTTPException(
            status_code=400,
            detail="Lesson start time must be before end time."
        )

    subject_query = (
        select(Subject)
        .where(Subject.id == lesson.subject_id, Subject.is_delete == False)
    )
    subject = session.exec(subject_query).first()

    if not subject:
        raise HTTPException(
            status_code=404,
            detail="Subject not found with the provided ID."
        )

    class_query = (
        select(Class)
        .where(Class.id == lesson.class_id, Class.is_delete == False)
    )
    related_class = session.exec(class_query).first()

    if not related_class:
        raise HTTPException(
            status_code=404,
            detail="Class not found with the provided ID."
        )

    teacher_query = (
        select(Teacher)
        .where(Teacher.id == lesson.teacher_id, Teacher.is_delete == False)
    )
    teacher = session.exec(teacher_query).first()

    if not teacher:
        raise HTTPException(
            status_code=404,
            detail="Teacher not found with the provided ID."
        )

    teacher_subject_ids = [s.id for s in teacher.subjects] if teacher.subjects else []
    if lesson.subject_id not in teacher_subject_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Teacher {teacher.first_name} {teacher.last_name} does not teach {subject.name}."
        )

    duplicate_name_query = (
        select(Lesson)
        .where(
            Lesson.name.ilike(f"%{name}%"),
            Lesson.class_id == lesson.class_id,
            Lesson.is_delete == False
        )
    )
    duplicate_name = session.exec(duplicate_name_query).first()

    if duplicate_name:
        raise HTTPException(
            status_code=400,
            detail=f"A lesson with similar name already exists for this class."
        )

    time_conflict_query = (
        select(Lesson)
        .where(
            Lesson.class_id == lesson.class_id,
            Lesson.day == lesson.day,
            Lesson.is_delete == False,
            or_(
                and_(
                    Lesson.start_time <= lesson.start_time,
                    Lesson.end_time > lesson.start_time
                ),
                and_(
                    Lesson.start_time < lesson.end_time,
                    Lesson.end_time >= lesson.end_time
                ),
                and_(
                    Lesson.start_time >= lesson.start_time,
                    Lesson.end_time <= lesson.end_time
                )
            )
        )
    )
    conflicting_lesson = session.exec(time_conflict_query).first()

    if conflicting_lesson:
        raise HTTPException(
            status_code=400,
            detail=f"Time conflict: Lesson '{conflicting_lesson.name}' is already scheduled for this class on {lesson.day} at the same time."
        )

    teacher_conflict_query = (
        select(Lesson)
        .where(
            Lesson.teacher_id == lesson.teacher_id,
            Lesson.day == lesson.day,
            Lesson.is_delete == False,
            or_(
                and_(
                    Lesson.start_time <= lesson.start_time,
                    Lesson.end_time > lesson.start_time
                ),
                and_(
                    Lesson.start_time < lesson.end_time,
                    Lesson.end_time >= lesson.end_time
                ),
                and_(
                    Lesson.start_time >= lesson.start_time,
                    Lesson.end_time <= lesson.end_time
                )
            )
        )
    )
    teacher_conflict = session.exec(teacher_conflict_query).first()

    if teacher_conflict:
        raise HTTPException(
            status_code=400,
            detail=f"Teacher conflict: {teacher.first_name} {teacher.last_name} is already teaching '{teacher_conflict.name}' on {lesson.day} at the same time."
        )

    new_lesson = Lesson(
        name=name,
        day=lesson.day,
        start_time=lesson.start_time,
        end_time=lesson.end_time,
        subject_id=lesson.subject_id,
        class_id=lesson.class_id,
        teacher_id=lesson.teacher_id,
        is_delete=False
    )

    session.add(new_lesson)

    try:
        session.flush()
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_lesson)

    return {
        "id": str(new_lesson.id),
        "message": "Lesson created successfully"
    }


def lessonUpdate(lesson: LessonUpdate, session: Session):
    findLessonQuery = (
        select(Lesson)
        .where(Lesson.id == lesson.id, Lesson.is_delete == False)
    )

    currentLesson: Optional[Lesson] = session.exec(findLessonQuery).first()

    if not currentLesson:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found with provided ID."
        )

    name = lesson.name.strip()

    if len(name) < 3:
        raise HTTPException(
            status_code=400,
            detail="Lesson name must be at least 3 characters long."
        )

    if lesson.start_time >= lesson.end_time:
        raise HTTPException(
            status_code=400,
            detail="Lesson start time must be before end time."
        )

    if lesson.subject_id != currentLesson.subject_id:
        subject_query = (
            select(Subject)
            .where(Subject.id == lesson.subject_id, Subject.is_delete == False)
        )
        subject = session.exec(subject_query).first()

        if not subject:
            raise HTTPException(
                status_code=404,
                detail="Subject not found with the provided ID."
            )

        currentLesson.subject_id = subject.id

    if lesson.class_id != currentLesson.class_id:
        class_query = (
            select(Class)
            .where(Class.id == lesson.class_id, Class.is_delete == False)
        )
        related_class = session.exec(class_query).first()

        if not related_class:
            raise HTTPException(
                status_code=404,
                detail="Class not found with the provided ID."
            )

        currentLesson.class_id = related_class.id

    if lesson.teacher_id != currentLesson.teacher_id:
        teacher_query = (
            select(Teacher)
            .where(Teacher.id == lesson.teacher_id, Teacher.is_delete == False)
        )
        teacher = session.exec(teacher_query).first()

        if not teacher:
            raise HTTPException(
                status_code=404,
                detail="Teacher not found with the provided ID."
            )

        teacher_subject_ids = [s.id for s in teacher.subjects] if teacher.subjects else []
        if currentLesson.subject_id not in teacher_subject_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Teacher {teacher.first_name} {teacher.last_name} does not teach this lesson."
            )

        currentLesson.teacher_id = teacher.id

    duplicate_name_query = (
        select(Lesson)
        .where(
            Lesson.name.ilike(f"%{name}%"),
            Lesson.class_id == lesson.class_id,
            Lesson.is_delete == False,
            Lesson.id != lesson.id
        )
    )
    duplicate_name = session.exec(duplicate_name_query).first()

    if duplicate_name:
        raise HTTPException(
            status_code=400,
            detail=f"A lesson with similar name already exists for this class."
        )

    time_conflict_query = (
        select(Lesson)
        .where(
            Lesson.class_id == lesson.class_id,
            Lesson.day == lesson.day,
            Lesson.is_delete == False,
            or_(
                and_(
                    Lesson.start_time <= lesson.start_time,
                    Lesson.end_time > lesson.start_time
                ),
                and_(
                    Lesson.start_time < lesson.end_time,
                    Lesson.end_time >= lesson.end_time
                ),
                and_(
                    Lesson.start_time >= lesson.start_time,
                    Lesson.end_time <= lesson.end_time
                )
            ),
            Lesson.id != lesson.id
        )
    )
    conflicting_lesson = session.exec(time_conflict_query).first()

    if conflicting_lesson:
        raise HTTPException(
            status_code=400,
            detail=f"Time conflict: Lesson '{conflicting_lesson.name}' is already scheduled for this class on {lesson.day} at the same time."
        )

    teacher_conflict_query = (
        select(Lesson)
        .where(
            Lesson.teacher_id == lesson.teacher_id,
            Lesson.day == lesson.day,
            Lesson.is_delete == False,
            or_(
                and_(
                    Lesson.start_time <= lesson.start_time,
                    Lesson.end_time > lesson.start_time
                ),
                and_(
                    Lesson.start_time < lesson.end_time,
                    Lesson.end_time >= lesson.end_time
                ),
                and_(
                    Lesson.start_time >= lesson.start_time,
                    Lesson.end_time <= lesson.end_time
                )
            ),
            Lesson.id != lesson.id
        )
    )
    teacher_conflict = session.exec(teacher_conflict_query).first()

    if teacher_conflict:
        raise HTTPException(
            status_code=400,
            detail=f"Teacher conflict: Teacher is already teaching '{teacher_conflict.name}' on {lesson.day} at the same time."
        )

    currentLesson.name = name
    currentLesson.day = lesson.day
    currentLesson.start_time = lesson.start_time
    currentLesson.end_time = lesson.end_time

    session.add(currentLesson)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error. Please check your data.")

    session.refresh(currentLesson)

    return {
        "id": str(currentLesson.id),
        "message": "Lesson updated successfully"
    }


def lessonSoftDelete(id: uuid.UUID, session: Session):
    findLessonQuery = (
        select(Lesson)
        .where(Lesson.id == id, Lesson.is_delete == False)
    )

    currentLesson: Optional[Lesson] = session.exec(findLessonQuery).first()

    if not currentLesson:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found with provided ID."
        )

    findRelatedExams = (
        select(Exam)
        .where(Exam.lesson_id == id, Exam.is_delete == False)
    )

    relatedExams = session.exec(findRelatedExams).all()

    exam_affected: int = 0
    for exam in relatedExams:
        exam.is_delete = True
        session.add(exam)
        exam_affected += 1

    findRelatedAssignment = (
        select(Assignment)
        .where(Assignment.lesson_id == id, Assignment.is_delete == False)
    )

    relatedAssignment = session.exec(findRelatedAssignment).all()

    assignment_affected: int = 0
    for assignment in relatedAssignment:
        assignment.is_delete = True
        session.add(assignment)
        assignment_affected += 1

    findRelatedAttendance = (
        select(Attendance)
        .where(Attendance.lesson_id == id, Attendance.is_delete == False)
    )

    relatedAttendance = session.exec(findRelatedAttendance).all()

    attendance_affected: int = 0
    for attendance in relatedAttendance:
        attendance.is_delete = True
        session.add(attendance)
        attendance_affected += 1

    currentLesson.is_delete = True
    session.add(currentLesson)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Error deleting lesson and related records.")

    session.refresh(currentLesson)

    return {
        "id": str(currentLesson.id),
        "message": "Lesson deleted successfully.",
        "exam_affected": exam_affected,
        "assignment_affected": assignment_affected,
        "attendance_affected": attendance_affected
    }
