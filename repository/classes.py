import uuid
from typing import Optional

from psycopg import IntegrityError
from fastapi import HTTPException
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Class, Teacher, Grade, Lesson, Student, Event, TeacherClassHistory
from repository.academicYear import getActiveAcademicYear
from schemas import ClassSave, ClassUpdateBase, PaginatedClassResponse


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Class.name).like(search_pattern)
        )

    return query


def getAllClassesIsDeleteFalse(session: Session, search: str, page: int, academic_year_id: Optional[uuid.UUID] = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Class.id.distinct()))
        .where(Class.is_delete == False)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    query = (
        select(Class)
        .where(Class.is_delete == False)
    )

    query = query.order_by(func.lower(Class.name))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_classes = session.exec(query).all()

    # (No per-teacher fallback here; admin class listing returns all classes. Assignment override happens below.)
    is_current_year = (academic_year_id == getActiveAcademicYear(session))

    # If academic year provided, attach assigned teacher for that year (history -> lessons -> supervisor)
    if academic_year_id and not is_current_year:
        active_year = getActiveAcademicYear(session)
        for c in all_classes:
            # Try TeacherClassHistory
            assigned = session.exec(
                select(Teacher)
                .join(TeacherClassHistory, TeacherClassHistory.teacher_id == Teacher.id)
                .where(
                    TeacherClassHistory.class_id == c.id,
                    TeacherClassHistory.academic_year_id == academic_year_id,
                    Teacher.is_delete == False,
                )
            ).first()

            # Fallback for active year: lesson-based or supervisor
            if not assigned and active_year and active_year.id == academic_year_id:
                assigned = session.exec(
                    select(Teacher)
                    .join(Lesson, Lesson.teacher_id == Teacher.id)
                    .where(
                        Lesson.class_id == c.id,
                        Lesson.academic_year_id == academic_year_id,
                        Teacher.is_delete == False,
                    )
                ).first()

            if not assigned and active_year and active_year.id == academic_year_id and c.supervisor_id:
                assigned = session.exec(
                    select(Teacher).where(Teacher.id == c.supervisor_id, Teacher.is_delete == False)
                ).first()

            # override supervisor field in response to reflect assignment for the selected year
            c.supervisor = assigned

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1)

    return PaginatedClassResponse(
        data=all_classes,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllClassesIsDeleteFalseAtOnce(session: Session):
    query = (
        select(Class)
        .where(
            Class.is_delete == False
        )
    )

    query = query.order_by(func.lower(Class.name))

    all_classes = session.exec(query).all()

    return all_classes


def countAllClassOfTheTeacher(teacherId: uuid.UUID, session: Session, academic_year_id: uuid.UUID = None):
    if academic_year_id:
        query = (
            select(func.count(TeacherClassHistory.class_id.distinct()))
            .where(
                TeacherClassHistory.teacher_id == teacherId,
                TeacherClassHistory.academic_year_id == academic_year_id,
            )
        )
    else:
        query = (
            select(func.count())
            .select_from(Class)
            .where(Class.supervisor_id == teacherId, Class.is_delete == False)
        )

    total_classes = session.exec(query).one()
    return total_classes


def getAllClassOfTeacherAndIsDeleteFalse(
    supervisorId: uuid.UUID,
    session: Session,
    search: str,
    page: int,
    academic_year_id: uuid.UUID = None,
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    if academic_year_id:
        count_query = (
            select(func.count(Class.id.distinct()))
            .join(TeacherClassHistory, TeacherClassHistory.class_id == Class.id)
            .where(
                TeacherClassHistory.teacher_id == supervisorId,
                TeacherClassHistory.academic_year_id == academic_year_id,
                Class.is_delete == False,
            )
        )
    else:
        count_query = (
            select(func.count(Class.id.distinct()))
            .where(
                Class.supervisor_id == supervisorId,
                Class.is_delete == False
            )
        )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    if academic_year_id:
        query = (
            select(Class)
            .join(TeacherClassHistory, TeacherClassHistory.class_id == Class.id)
            .where(
                TeacherClassHistory.teacher_id == supervisorId,
                TeacherClassHistory.academic_year_id == academic_year_id,
                Class.is_delete == False,
            )
        )
    else:
        query = (
            select(Class)
            .where(
                Class.supervisor_id == supervisorId,
                Class.is_delete == False,
            )
        )

    query = query.order_by(func.lower(Class.name))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_classes = session.exec(query).all()

    # If we used fallback for active year, adjust total_count to match returned results
    if academic_year_id and total_count == 0 and all_classes:
        total_count = len(all_classes)

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1)

    return PaginatedClassResponse(
        data=all_classes,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getClassOfStudentAndIsDeleteFalse(studentId: uuid.UUID, session: Session):
    query = (
        select(Class)
        .join(
            Student, Class.id == Student.class_id,
        )
        .where(
            Student.id == studentId,
            Class.is_delete == False,
            Student.is_delete == False
        )
    )

    student_class: Optional[Class] = session.exec(query).first()

    if student_class is None:
        raise HTTPException(status_code=404, detail="No class found with the provided ID.")

    return student_class


def findClassById(classId: uuid.UUID, session: Session):
    query = (
        select(Class)
        .where(Class.id == classId, Class.is_delete == False)
    )

    classes = session.exec(query).first()

    if classes is None:
        raise HTTPException(status_code=404, detail="No class found with the provided ID.")

    return classes


def classSave(classes: ClassSave, session: Session):
    query = (
        select(Class)
        .where(func.lower(Class.name) == classes.name.lower(), Class.is_delete == False)
    )

    existing = session.exec(query).first()

    if existing:
        raise HTTPException(status_code=400, detail="Class already exists")

    supervisorId = classes.supervisorId
    gradeId = classes.gradeId

    if supervisorId:
        teacher_query = (
            select(Teacher)
            .where(Teacher.id == supervisorId, Teacher.is_delete == False)
        )

        teacher = session.exec(teacher_query).first()

        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail=f"No teacher found with the provided ID: {supervisorId}"
            )

    grade_query = (
        select(Grade)
        .where(Grade.id == gradeId, Grade.is_delete == False)
    )
    grade = session.exec(grade_query).first()

    if grade is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Grade found with the provided ID: {gradeId}"
        )

    new_class = Class(
        name=classes.name,
        capacity=classes.capacity,
        supervisor_id=supervisorId,
        grade_id=gradeId,
    )

    session.add(new_class)

    try:
        session.flush()  # ensure new_subject.id is generated
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Class already exists (unique constraint)")

    session.refresh(new_class)

    return {
        "id": str(new_class.id),
        "message": "Class created successfully",
    }


def ClassUpdate(classes: ClassUpdateBase, session: Session):
    findClassQuery = (
        select(Class)
        .where(Class.id == classes.id, Class.is_delete == False)
    )

    currentClass = session.exec(findClassQuery).first()

    if currentClass is None:
        raise HTTPException(status_code=404, detail="No Class found with the provided ID.")

    findSameNameClassQuery = (
        select(Class)
        .where(func.lower(Class.name) == classes.name.lower(), Class.is_delete == False, Class.id != classes.id)
    )

    existing = session.exec(findSameNameClassQuery).first()

    if existing:
        raise HTTPException(status_code=400, detail="A class with the same name already exists.")

    supervisorId = classes.supervisorId
    gradeId = classes.gradeId

    if supervisorId:
        teacher_query = (
            select(Teacher)
            .where(Teacher.id == supervisorId, Teacher.is_delete == False)
        )

        teacher = session.exec(teacher_query).first()

        if teacher is None:
            raise HTTPException(
                status_code=404,
                detail=f"No teacher found with the provided ID: {supervisorId}"
            )

    grade_query = (
        select(Grade)
        .where(Grade.id == gradeId, Grade.is_delete == False)
    )
    grade = session.exec(grade_query).first()

    if grade is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Grade found with the provided ID: {gradeId}"
        )

    currentClass.name = classes.name
    currentClass.capacity = classes.capacity
    currentClass.supervisor_id = classes.supervisorId
    currentClass.grade_id = classes.gradeId

    session.add(currentClass)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Class already exists (unique constraint)")

    session.refresh(currentClass)

    return {
        "id": str(currentClass.id),
        "message": "Class updated successfully",
    }


def ClassSoftDeleteWithLessonsStudentsEventsAnnoucements(id: uuid.UUID, session: Session):
    result = (
        select(Class)
        .where(Class.id == id, Class.is_delete == False)
    )
    current_class = session.exec(result).first()

    if current_class is None:
        raise HTTPException(status_code=404, detail="No class found with the provided ID.")

    # Check if any active students are linked to this class
    students = [s for s in current_class.students if not s.is_delete]
    if students:
        return {
            "id": str(current_class.id),
            "message": "Class cannot be deleted while students are enrolled. Please reassign or remove students first.",
            "lessons_affected": 0,
            "students_affected": len(students),
            "events_affected": 0,
            "announcements_affected": 0
        }

    current_class.supervisor_id = None

    lessons = current_class.lessons  # using relationship directly

    for lesson in lessons:
        lesson.is_delete = True

    events = current_class.events

    for event in events:
        event.is_delete = True

    announcements = current_class.announcements

    for announcement in announcements:
        announcement.is_delete = True

    current_class.is_delete = True

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Error deleting class and its related data")

    session.refresh(current_class)

    return {
        "id": str(current_class.id),
        "message": "Class deleted successfully",
        "lessons_affected": len(lessons),
        "students_affected": 0,
        "events_affected": len(events),
        "announcements_affected": len(announcements)
    }
