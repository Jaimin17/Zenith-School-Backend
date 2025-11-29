import re
import uuid
from typing import List, Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import func, Select, or_
from sqlmodel import Session, select

from core.config import settings
from models import Teacher, Lesson, Subject, Class
from schemas import TeacherSave, TeacherUpdateBase

PHONE_RE = re.compile(r'^[6-9]\d{9}$')


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
    username = teacher.username.strip()
    email = teacher.email.strip().lower()
    phone = teacher.phone.strip()

    if not PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail="Invalid Indian phone number. Must be 10 digits starting with 6-9.")

    duplicate_query = (
        select(Teacher)
        .where(
            or_(
                func.lower(func.trim(Teacher.username)) == username.lower(),
                func.lower(func.trim(Teacher.email)) == email,
                func.trim(Teacher.phone) == phone
            ),
            Teacher.is_delete == False
        )
    )

    existing = session.exec(duplicate_query).first()

    if existing:
        raise HTTPException(status_code=400, detail="Teacher exists with same username, email, or phone.")

    subject_ids = teacher.subjects or []
    subjects = []

    if subject_ids:
        # Convert all IDs to UUID objects safely
        normalized_ids = []
        for sid in subject_ids:
            try:
                normalized_ids.append(uuid.UUID(str(sid)))
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid subject ID: {sid}")

        subject_query = (
            select(Subject)
            .where(Subject.id.in_(normalized_ids), Subject.is_delete == False)
        )

        subjects = session.exec(subject_query).all()
        found_ids = {s.id for s in subjects}

        missing = [str(sid) for sid in normalized_ids if sid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"No subject(s) found with ID(s): {', '.join(missing)}"
            )

    new_teacher = Teacher(
        username=username,
        first_name=teacher.first_name.strip(),
        last_name=teacher.last_name.strip(),
        email=email,
        phone=phone,
        address=teacher.address.strip(),
        img=teacher.img,
        blood_type=teacher.blood_type,
        sex=teacher.sex,
        is_delete=False,
        password="user@123"  # or generate one, depending on your logic
    )

    new_teacher.subjects = subjects

    session.add(new_teacher)

    try:
        session.flush()  # ensure new_subject.id is generated
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Unique constraint violated (username/email/phone already exists).")

    session.refresh(new_teacher)

    return {
        "id": str(new_teacher.id),
        "message": "Teacher created successfully"
    }


def TeacherUpdate(teacher: TeacherUpdateBase, session: Session):
    findTeacherQuery = (
        select(Teacher)
        .where(Teacher.id == teacher.id, Teacher.is_delete == False)
    )

    currentTeacher = session.exec(findTeacherQuery).first()

    if currentTeacher is None:
        raise HTTPException(status_code=404, detail="No teacher found with the provided ID.")

    new_username = teacher.username.strip()
    new_email = teacher.email.strip().lower()
    new_phone = teacher.phone.strip()

    if not PHONE_RE.match(new_phone):
        raise HTTPException(status_code=400, detail="Invalid Indian phone number. Must be 10 digits starting with 6-9.")

    findSameNameTeacherquery = (
        select(Teacher)
        .where(
            or_(
                func.lower(func.trim(Teacher.username)) == new_username.lower(),
                func.lower(func.trim(Teacher.email)) == new_email,
                func.trim(Teacher.phone) == new_phone
            ),
            Teacher.is_delete == False,
            Teacher.id != teacher.id
        )
    )

    existing = session.exec(findSameNameTeacherquery).first()

    if existing:
        raise HTTPException(status_code=400, detail="A teacher with the same username, email, or phone already exists.")

    subject_ids = teacher.subjects or []
    subjects: List[Subject] = []

    if subject_ids:
        # ensure all are UUID objects
        normalized_ids: List[uuid.UUID] = []
        for sid in subject_ids:
            if isinstance(sid, uuid.UUID):
                normalized_ids.append(sid)
            else:
                try:
                    normalized_ids.append(uuid.UUID(str(sid)))
                except Exception:
                    raise HTTPException(status_code=400, detail=f"Invalid subject id: {sid}")

        subject_query = select(Subject).where(Subject.id.in_(normalized_ids), Subject.is_delete == False)
        subjects = session.exec(subject_query).all()
        found_ids = {s.id for s in subjects}

        missing = [str(sid) for sid in normalized_ids if sid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"No subject(s) found with ID(s): {', '.join(missing)}"
            )

    currentTeacher.username = new_username
    currentTeacher.first_name = teacher.first_name
    currentTeacher.last_name = teacher.last_name
    currentTeacher.email = new_email
    currentTeacher.phone = new_phone
    currentTeacher.address = teacher.address.strip()
    currentTeacher.img = teacher.img
    currentTeacher.blood_type = teacher.blood_type
    currentTeacher.sex = teacher.sex
    currentTeacher.subjects = subjects

    session.add(currentTeacher)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Unique constraint violated (username/email/phone).")

    session.refresh(currentTeacher)

    return {
        "id": str(currentTeacher.id),
        "message": "Teacher updated successfully"
    }


def teacherSoftDeleteWithLessonAndClassAndSubject(id: uuid.UUID, session: Session):
    findTeacher = (
        select(Teacher)
        .where(Teacher.id == id, Teacher.is_delete == False)
    )

    currentTeacher: Optional[Teacher] = session.exec(findTeacher).first()

    if currentTeacher is None:
        raise HTTPException(status_code=404, detail="No teacher found with the provided ID.")

    class_query = (
        select(Class)
        .where(Class.supervisor_id == id, Class.is_delete == False)
    )
    active_classes: List[Class] = session.exec(class_query).all()
    class_affected = len(active_classes)

    if class_affected > 0:
        # Do not delete if linked with any class
        return {
            "id": str(currentTeacher.id),
            "message": "Teacher cannot be deleted while assigned as supervisor to one or more active classes.",
            "subject_affected": 0,
            "lesson_affected": 0,
            "class_affected": class_affected
        }

    subject_count = len(currentTeacher.subjects) if currentTeacher.subjects else 0
    currentTeacher.subjects = []

    lesson_query = (
        select(Lesson)
        .where(Lesson.teacher_id == id, Lesson.is_delete == False)
    )
    lessons: List[Lesson] = session.exec(lesson_query).all()
    lesson_count = 0
    for lesson in lessons:
        lesson.is_delete = True
        session.add(lesson)
        lesson_count += 1

    currentTeacher.is_delete = True
    session.add(currentTeacher)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Error deleting teacher and related records.")
        # refresh to get latest relationships (optional)
    session.refresh(currentTeacher)

    return {
        "id": str(currentTeacher.id),
        "message": "Teacher soft-deleted successfully.",
        "subject_affected": subject_count,
        "lesson_affected": lesson_count,
        "class_affected": 0
    }
