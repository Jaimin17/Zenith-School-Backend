import uuid

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import func, Select
from sqlmodel import Session, select

from core.config import settings
from models import Teacher, Lesson, Subject
from schemas import TeacherSave, TeacherUpdateBase


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Teacher.username).like(search_pattern)) |
            (func.lower(Teacher.first_name).like(search_pattern)) |
            (func.lower(Teacher.last_name).like(search_pattern))
        )

    return query


def countTeacher(session: Session):
    return session.exec(
        select(func.count()).select_from(Teacher).where(Teacher.is_delete == False)
    ).first()


def getAllTeachersIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Teacher)
        .where(Teacher.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_teachers = session.exec(query).all()
    return active_teachers


def getAllTeachersOfClassAndIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Teacher)
        .join(
            Lesson,
            onclause=(Lesson.teacher_id == Teacher.id)
        )
        .where(
            Lesson.class_id == classId,
            Teacher.is_delete == False,
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE).distinct()
    results = session.exec(query).all()
    return results


def findTeacherById(teacherId: uuid.UUID, session: Session):
    query = (
        select(Teacher)
        .where(Teacher.id == teacherId, Teacher.is_delete == False)
    )
    teacher = session.exec(query).first()

    if teacher is None:
        raise HTTPException(status_code=404, detail="No teacher found with provided ID.")

    return teacher


def teacherSave(teacher: TeacherSave, session: Session):
    query = (
        select(Teacher)
        .where(func.lower(Teacher.username) == teacher.username.lower(), Teacher.is_delete == False)
    )

    existing = session.exec(query).first()

    if existing:
        raise HTTPException(status_code=400, detail="Teacher already exists with the same username.")

    subject_ids = teacher.subjects or []

    if subject_ids:
        subject_query = (
            select(Subject)
            .where(Subject.id.in_(subject_ids), Subject.is_delete == False)
        )

        subjects = session.exec(subject_query).all()
        found_ids = {s.id for s in subjects}

        missing = [str(sid) for sid in subject_ids if sid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"No subject(s) found with ID(s): {', '.join(missing)}"
            )
    else:
        subjects = []

    new_teacher = Teacher(
        username=teacher.username,
        first_name=teacher.first_name,
        last_name=teacher.last_name,
        email=teacher.email,
        phone=teacher.phone,
        address=teacher.address,
        img=teacher.img,
        blood_type=teacher.blood_type,
        sex=teacher.sex,
        is_delete=False
    )

    new_teacher.subjects = subjects

    session.add(new_teacher)

    try:
        session.flush()  # ensure new_subject.id is generated
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Teacher creation failed due to a unique constraint violation.")

    session.refresh(new_teacher)

    return {
        "id": str(new_teacher.id),
        "message": "Teacher created successfully"
    }


# def TeacherUpdate(teacher: TeacherUpdateBase, session: Session):