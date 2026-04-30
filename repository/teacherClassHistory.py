import uuid
from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from models import AcademicYear, Class, Teacher, TeacherClassHistory, Lesson


def getTeacherClassHistoryByYear(
    teacher_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    session: Session,
) -> Optional[TeacherClassHistory]:
    return session.exec(
        select(TeacherClassHistory).where(
            TeacherClassHistory.teacher_id == teacher_id,
            TeacherClassHistory.academic_year_id == academic_year_id,
        )
    ).first()


def createTeacherClassHistory(
    teacher_id: uuid.UUID,
    class_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    session: Session,
) -> TeacherClassHistory:
    existing = session.exec(
        select(TeacherClassHistory).where(
            TeacherClassHistory.teacher_id == teacher_id,
            TeacherClassHistory.class_id == class_id,
            TeacherClassHistory.academic_year_id == academic_year_id,
        )
    ).first()
    if existing:
        return existing

    record = TeacherClassHistory(
        teacher_id=teacher_id,
        class_id=class_id,
        academic_year_id=academic_year_id,
    )
    session.add(record)
    return record


def getTeacherClassesForYear(
    teacher_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    session: Session,
) -> List[Class]:
    query = (
        select(Class)
        .join(
            TeacherClassHistory,
            TeacherClassHistory.class_id == Class.id,
        )
        .where(
            TeacherClassHistory.teacher_id == teacher_id,
            TeacherClassHistory.academic_year_id == academic_year_id,
            Class.is_delete == False,
        )
        .order_by(Class.name)
    )
    return session.exec(query).all()


def getTeacherOfClassForYear(
    class_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    session: Session,
) -> Optional[Teacher]:
    query = (
        select(Teacher)
        .join(
            TeacherClassHistory,
            TeacherClassHistory.teacher_id == Teacher.id,
        )
        .where(
            TeacherClassHistory.class_id == class_id,
            TeacherClassHistory.academic_year_id == academic_year_id,
            Teacher.is_delete == False,
        )
    )
    return session.exec(query).first()


def seedTeacherClassHistoryToAcademicYear(
    academic_year_id: uuid.UUID,
    session: Session,
) -> dict:
    target_year = session.exec(
        select(AcademicYear).where(
            AcademicYear.id == academic_year_id,
            AcademicYear.is_delete == False,
        )
    ).first()
    if not target_year:
        raise HTTPException(status_code=404, detail="Academic year not found.")

    # Get all lessons for this academic year to extract teacher-class-subject combinations
    lessons = session.exec(
        select(Lesson).where(
            Lesson.academic_year_id == academic_year_id,
            Lesson.is_delete == False,
            Lesson.teacher_id.is_not(None),
            Lesson.class_id.is_not(None),
        )
    ).all()

    # Extract unique (teacher_id, class_id) combinations
    seen_combinations = set()
    created = 0
    skipped = 0

    for lesson in lessons:
        # Create a unique key for this combination
        combo_key = (lesson.teacher_id, lesson.class_id)
        
        # Skip if we've already processed this combination in this seed operation
        if combo_key in seen_combinations:
            continue
        
        seen_combinations.add(combo_key)

        # Check if this combination already exists in TeacherClassHistory for this year
        existing = session.exec(
            select(TeacherClassHistory).where(
                TeacherClassHistory.teacher_id == lesson.teacher_id,
                TeacherClassHistory.class_id == lesson.class_id,
                TeacherClassHistory.academic_year_id == academic_year_id,
            )
        ).first()
        
        if existing:
            skipped += 1
            continue

        # Create new TeacherClassHistory record
        session.add(
            TeacherClassHistory(
                teacher_id=lesson.teacher_id,
                class_id=lesson.class_id,
                academic_year_id=academic_year_id,
            )
        )
        created += 1

    session.commit()
    return {"created": created, "skipped": skipped}
