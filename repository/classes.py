import uuid
from typing import Optional

from psycopg import IntegrityError
from fastapi import HTTPException
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Class, Teacher, Grade, Lesson, Student, Event
from schemas import ClassSave, ClassUpdateBase


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Class.name).like(search_pattern)
        )

    return query


def getAllClassesIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Class)
        .where(Class.is_delete == False)
    )

    query = query.order_by(func.lower(Class.name))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_classes = session.exec(query).all()
    return all_classes


def countAllClassOfTheTeacher(teacherId: uuid.UUID, session: Session):
    query = (
        select(func.count())
        .select_from(Class)
        .where(Class.supervisor_id == teacherId, Class.is_delete == False)
    )

    total_classes = session.exec(query).one()
    return total_classes


def getAllClassOfTeacherAndIsDeleteFalse(supervisorId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

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
    return all_classes


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

    new_class = Class(
        name=classes.name,
        capacity=classes.capacity,
        supervisor_id=supervisorId,
        grade_id=gradeId,
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

    current_class.supervisor_id = None

    lessons = current_class.lessons  # using relationship directly

    for lesson in lessons:
        lesson.is_delete = True

    students = current_class.students

    for student in students:
        student.class_id = None  # unlink class
        student.is_delete = True  # soft delete student

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
        "students_affected": len(students),
        "events_affected": len(events),
        "announcements_affected": len(announcements)
    }
