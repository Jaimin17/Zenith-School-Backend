import re
import uuid
from typing import List, Optional

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlalchemy import func, Select, or_
from sqlmodel import Session, select
import os

from core.FileStorage import process_and_save_image, cleanup_image
from core.config import settings
from models import Teacher, Lesson, Subject, Class
from schemas import PaginatedTeacherResponse


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

    query = query.order_by(func.lower(Teacher.username))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_teachers = session.exec(query).all()
    return active_teachers


def getAllTeachersListIsDeleteFalse(session: Session):
    query = (
        select(Teacher)
        .where(Teacher.is_delete == False)
    )

    query = query.order_by(func.lower(Teacher.username))
    active_teachers = session.exec(query).all()
    return active_teachers


def getTotalTeachersCount(session: Session, search: str = None) -> int:
    query = (
        select(func.count(Teacher.id))
        .where(Teacher.is_delete == False)
    )

    # Add search if provided
    query = addSearchOption(query, search)

    total_count = session.exec(query).one()
    return total_count


def getAllTeachersOfClassAndIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Teacher.id.distinct()))
        .join(
            Lesson,
            onclause=(Lesson.teacher_id == Teacher.id)
        )
        .where(
            Lesson.class_id == classId,
            Teacher.is_delete == False,
        )
    )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

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
        .distinct()  # Explicitly add distinct to get unique teachers
    )

    query = addSearchOption(query, search)

    # Order by username directly (not using func.lower in ORDER BY)
    query = query.order_by(Teacher.username)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    results = session.exec(query).all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedTeacherResponse(
        data=results,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def findTeacherById(teacherId: uuid.UUID, session: Session):
    query = (
        select(Teacher)
        .where(Teacher.id == teacherId, Teacher.is_delete == False)
    )
    teacher = session.exec(query).first()

    if teacher is None:
        raise HTTPException(status_code=404, detail="No teacher found with provided ID.")

    return teacher


async def teacherSaveWithImage(teacher_data: dict, img: Optional[UploadFile], session: Session):
    username = teacher_data["username"].strip()
    email = teacher_data["email"].strip().lower()
    phone = teacher_data["phone"].strip()

    if not settings.EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid Email address.")

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
        if existing.username.lower() == username.lower():
            raise HTTPException(status_code=400, detail="Username already exists.")
        elif existing.email.lower() == email:
            raise HTTPException(status_code=400, detail="Email already exists.")
        else:
            raise HTTPException(status_code=400, detail="Phone number already exists.")

    subject_ids = teacher_data["subjects"] or []
    subjects = []

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
                detail=f"Subject(s) not found with ID(s): {', '.join(missing)}"
            )

    image_filename = None
    if img and img.filename:
        try:
            image_filename = await process_and_save_image(img, "teachers", username)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    new_teacher = Teacher(
        username=username,
        first_name=teacher_data["first_name"].strip(),
        last_name=teacher_data["last_name"].strip(),
        email=email,
        phone=phone,
        address=teacher_data["address"].strip(),
        img=image_filename,  # Save filename/path
        blood_type=teacher_data["blood_type"],
        sex=teacher_data["sex"],
        dob=teacher_data["dob"],
        is_delete=False,
        password="user@123"
    )

    new_teacher.subjects = subjects

    session.add(new_teacher)

    try:
        session.flush()  # ensure new_subject.id is generated
        session.commit()
    except IntegrityError as e:
        session.rollback()
        # Delete uploaded image if database fails
        if image_filename:
            try:
                os.remove(settings.UPLOAD_DIR_DP / "teachers" / image_filename)
            except:
                pass
        raise HTTPException(
            status_code=400,
            detail="Database error. Username, email, or phone already exists."
        )
    session.refresh(new_teacher)

    return {
        "id": str(new_teacher.id),
        "message": "Teacher created successfully"
    }


async def TeacherUpdate(teacher_data: dict, img: Optional[UploadFile], session: Session):
    file_name = img
    print(file_name)

    findTeacherQuery = (
        select(Teacher)
        .where(Teacher.id == teacher_data["id"], Teacher.is_delete == False)
    )

    currentTeacher = session.exec(findTeacherQuery).first()

    if currentTeacher is None:
        raise HTTPException(status_code=404, detail="No teacher found with the provided ID.")

    new_username = teacher_data["username"].strip()
    new_email = teacher_data["email"].strip().lower()
    new_phone = teacher_data["phone"].strip()

    if not settings.PHONE_RE.match(new_phone):
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
            Teacher.id != teacher_data["id"]
        )
    )

    existing = session.exec(findSameNameTeacherquery).first()

    if existing:
        raise HTTPException(status_code=400, detail="A teacher with the same username, email, or phone already exists.")

    subject_ids = teacher_data["subjects"] or []
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

    image_filename = currentTeacher.img
    if img and img.filename:
        try:
            image_filename = await process_and_save_image(img, "teachers", new_username)

            if currentTeacher.img and currentTeacher.img != image_filename:
                old_image_path = settings.UPLOAD_DIR_DP / "teachers" / currentTeacher.img
                cleanup_image(old_image_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    currentTeacher.username = new_username
    currentTeacher.first_name = teacher_data["first_name"]
    currentTeacher.last_name = teacher_data["last_name"]
    currentTeacher.email = new_email
    currentTeacher.phone = new_phone
    currentTeacher.address = teacher_data["address"].strip()
    currentTeacher.img = image_filename
    currentTeacher.blood_type = teacher_data["blood_type"]
    currentTeacher.sex = teacher_data["sex"]
    currentTeacher.dob = teacher_data["dob"]
    currentTeacher.subjects = subjects

    session.add(currentTeacher)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()

        # If we uploaded a new image but commit failed, clean it up
        if img and img.filename and image_filename:
            new_image_path = settings.UPLOAD_DIR_DP / "teachers" / image_filename
            cleanup_image(new_image_path)
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
