import uuid
from typing import Optional, List

from fastapi import HTTPException
from sqlmodel import Session, select

from models import StudentClassHistory, AcademicYear, Class, Grade, Lesson, Student
from models import StudentStatus
from schemas import StudentClassHistoryRead, StudentHistoryResponse, SeedStudentsResponse


def getStudentClassHistoryByYear(
    student_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    session: Session,
) -> Optional[StudentClassHistory]:
    return session.exec(
        select(StudentClassHistory).where(
            StudentClassHistory.student_id == student_id,
            StudentClassHistory.academic_year_id == academic_year_id,
        )
    ).first()


def createStudentClassHistory(
    student_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    class_id: Optional[uuid.UUID],
    grade_id: Optional[uuid.UUID],
    session: Session,
) -> StudentClassHistory:
    # Idempotent: skip if already exists
    existing = getStudentClassHistoryByYear(student_id, academic_year_id, session)
    if existing:
        return existing

    record = StudentClassHistory(
        student_id=student_id,
        academic_year_id=academic_year_id,
        class_id=class_id,
        grade_id=grade_id,
    )
    session.add(record)
    # Caller is responsible for commit
    return record


def updateStudentClassHistoryClassId(
    student_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    new_class_id: uuid.UUID,
    session: Session,
) -> Optional[StudentClassHistory]:
    """Update class_id in an existing history record (used after manual assign-class override)."""
    record = getStudentClassHistoryByYear(student_id, academic_year_id, session)
    if record:
        record.class_id = new_class_id
        session.add(record)
    return record


def getStudentFullHistory(student_id: uuid.UUID, session: Session) -> List[StudentClassHistoryRead]:
    records = session.exec(
        select(StudentClassHistory)
        .where(StudentClassHistory.student_id == student_id)
        .order_by(StudentClassHistory.created_at.desc())
    ).all()

    result = []
    for rec in records:
        # Resolve class name and grade level for convenience
        class_name = None
        grade_level = None
        if rec.class_id:
            cls = session.get(Class, rec.class_id)
            class_name = cls.name if cls else None
        if rec.grade_id:
            grade = session.get(Grade, rec.grade_id)
            grade_level = grade.level if grade else None

        year = session.get(AcademicYear, rec.academic_year_id)

        result.append(StudentClassHistoryRead(
            id=rec.id,
            student_id=rec.student_id,
            academic_year_id=rec.academic_year_id,
            academic_year=year,
            class_id=rec.class_id,
            grade_id=rec.grade_id,
            class_name=class_name,
            grade_level=grade_level,
            created_at=rec.created_at,
        ))
    return result


def getHistoricalLessons(
    student_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    session: Session,
) -> List[Lesson]:
    """Return all lessons for the class the student was in during the given academic year."""
    history = getStudentClassHistoryByYear(student_id, academic_year_id, session)
    if not history or not history.class_id:
        return []

    lessons = session.exec(
        select(Lesson).where(
            Lesson.class_id == history.class_id,
            Lesson.academic_year_id == academic_year_id,
            Lesson.is_delete == False,
        )
    ).all()
    return lessons


def seedStudentsToAcademicYear(academic_year_id: uuid.UUID, session: Session) -> SeedStudentsResponse:
    """Create StudentClassHistory records for every active, non-deleted student
    in the given academic year, using their current class_id / grade_id.
    Already-existing records are skipped (idempotent)."""
    year = session.get(AcademicYear, academic_year_id)
    if not year or year.is_delete:
        raise HTTPException(status_code=404, detail="Academic year not found.")

    students = session.exec(
        select(Student).where(
            Student.is_delete == False,
            Student.status == StudentStatus.ACTIVE,
        )
    ).all()

    created = 0
    skipped = 0

    for student in students:
        existing = session.exec(
            select(StudentClassHistory).where(
                StudentClassHistory.student_id == student.id,
                StudentClassHistory.academic_year_id == academic_year_id,
            )
        ).first()
        if existing:
            skipped += 1
            continue

        record = StudentClassHistory(
            student_id=student.id,
            academic_year_id=academic_year_id,
            class_id=student.class_id,
            grade_id=student.grade_id,
        )
        session.add(record)
        created += 1

    session.commit()
    return SeedStudentsResponse(created=created, skipped=skipped)
