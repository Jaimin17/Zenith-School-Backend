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
from core.security import get_password_hash
from models import Teacher, Lesson, Subject, Class, TeacherClassHistory
from repository.academicYear import getActiveAcademicYear
from schemas import PaginatedTeacherResponse, updatePasswordModel


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


def _attach_year_scoped_data(
    teachers: List[Teacher],
    academic_year_id: Optional[uuid.UUID],
    session: Session,
) -> List[Teacher]:
    if not academic_year_id:
        return teachers

    for teacher in teachers:
        classes = session.exec(
            select(Class)
            .join(TeacherClassHistory, TeacherClassHistory.class_id == Class.id)
            .where(
                TeacherClassHistory.teacher_id == teacher.id,
                TeacherClassHistory.academic_year_id == academic_year_id,
                Class.is_delete == False,
            )
            .order_by(Class.name)
        ).all()

        # Fallback for active year: if no history rows exist for this year, derive from lessons or current supervisor
        if not classes:
            active_year = getActiveAcademicYear(session)
            if active_year and active_year.id == academic_year_id:
                # from lessons (distinct classes)
                lesson_classes = session.exec(
                    select(Class)
                    .join(Lesson, Lesson.class_id == Class.id)
                    .where(
                        Lesson.teacher_id == teacher.id,
                        Lesson.academic_year_id == academic_year_id,
                        Class.is_delete == False,
                    )
                    .distinct()
                ).all()

                # from supervisor assignment
                supervisor_classes = session.exec(
                    select(Class).where(
                        Class.supervisor_id == teacher.id,
                        Class.is_delete == False,
                    )
                ).all()

                # merge unique classes preserving ordering by name
                class_map = {c.id: c for c in lesson_classes}
                for c in supervisor_classes:
                    class_map.setdefault(c.id, c)

                classes = sorted(class_map.values(), key=lambda c: (c.name or ""))

        lessons = session.exec(
            select(Lesson).where(
                Lesson.teacher_id == teacher.id,
                Lesson.academic_year_id == academic_year_id,
                Lesson.is_delete == False,
            )
        ).all()

        subjects: List[Subject] = []
        seen_subjects = set()
        for lesson in lessons:
            if lesson.subject and lesson.subject.id not in seen_subjects:
                subjects.append(lesson.subject)
                seen_subjects.add(lesson.subject.id)

        teacher.classes = classes
        teacher.lessons = lessons
        teacher.subjects = subjects

    return teachers


def _resolve_year_scope(
    academic_year_id: Optional[uuid.UUID],
    session: Session,
) -> tuple[Optional[uuid.UUID], Optional[uuid.UUID]]:
    if not academic_year_id:
        return None, None

    active_year = getActiveAcademicYear(session)
    if active_year and active_year.id == academic_year_id:
        # Show all teachers for the active year, but keep year-scoped data attached.
        return None, academic_year_id

    return academic_year_id, academic_year_id


def getAllTeachersIsDeleteFalse(
    session: Session,
    search: str,
    page: int,
    academic_year_id: Optional[uuid.UUID] = None,
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    filter_year_id, attach_year_id = _resolve_year_scope(academic_year_id, session)

    if filter_year_id:
        query = (
            select(Teacher)
            .join(TeacherClassHistory, TeacherClassHistory.teacher_id == Teacher.id)
            .where(
                Teacher.is_delete == False,
                TeacherClassHistory.academic_year_id == filter_year_id,
            )
            .distinct()
        )
    else:
        query = (
            select(Teacher)
            .where(Teacher.is_delete == False)
        )


    query = addSearchOption(query, search)

    if filter_year_id:
        query = query.order_by(Teacher.username)
    else:
        query = query.order_by(func.lower(Teacher.username))

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_teachers = session.exec(query).all()
    return _attach_year_scoped_data(active_teachers, attach_year_id, session)


def getAllTeachersListIsDeleteFalse(session: Session, academic_year_id: Optional[uuid.UUID] = None):
    filter_year_id, attach_year_id = _resolve_year_scope(academic_year_id, session)

    if filter_year_id:
        query = (
            select(Teacher)
            .join(TeacherClassHistory, TeacherClassHistory.teacher_id == Teacher.id)
            .where(
                Teacher.is_delete == False,
                TeacherClassHistory.academic_year_id == filter_year_id,
            )
            .distinct()
        )
    else:
        query = (
            select(Teacher)
            .where(Teacher.is_delete == False)
        )

    if filter_year_id:
        query = query.order_by(Teacher.username)
    else:
        query = query.order_by(func.lower(Teacher.username))
    active_teachers = session.exec(query).all()
    return _attach_year_scoped_data(active_teachers, attach_year_id, session)


def getTotalTeachersCount(
    session: Session,
    search: str = None,
    academic_year_id: Optional[uuid.UUID] = None,
) -> int:
    filter_year_id, _ = _resolve_year_scope(academic_year_id, session)

    if filter_year_id:
        query = (
            select(func.count(func.distinct(Teacher.id)))
            .join(TeacherClassHistory, TeacherClassHistory.teacher_id == Teacher.id)
            .where(
                Teacher.is_delete == False,
                TeacherClassHistory.academic_year_id == filter_year_id,
            )
        )
    else:
        query = (
            select(func.count(Teacher.id))
            .where(Teacher.is_delete == False)
        )

    # Add search if provided
    query = addSearchOption(query, search)

    total_count = session.exec(query).one()
    return total_count


def getAllTeachersOfClassAndIsDeleteFalse(
    classId: uuid.UUID,
    session: Session,
    search: str,
    page: int,
    academic_year_id: uuid.UUID = None,
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    if academic_year_id:
        count_query = (
            select(func.count(Teacher.id.distinct()))
            .join(TeacherClassHistory, TeacherClassHistory.teacher_id == Teacher.id)
            .where(
                TeacherClassHistory.class_id == classId,
                TeacherClassHistory.academic_year_id == academic_year_id,
                Teacher.is_delete == False,
            )
        )
    else:
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

    if academic_year_id:
        query = (
            select(Teacher)
            .join(TeacherClassHistory, TeacherClassHistory.teacher_id == Teacher.id)
            .where(
                TeacherClassHistory.class_id == classId,
                TeacherClassHistory.academic_year_id == academic_year_id,
                Teacher.is_delete == False,
            )
            .distinct()
        )
    else:
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

    results = _attach_year_scoped_data(results, academic_year_id, session)

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


def findTeacherByIdYearScoped(
    teacherId: uuid.UUID,
    session: Session,
    academic_year_id: Optional[uuid.UUID] = None,
):
    teacher = findTeacherById(teacherId, session)
    _, attach_year_id = _resolve_year_scope(academic_year_id, session)
    return _attach_year_scoped_data([teacher], attach_year_id, session)[0]


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

    hashed_password = get_password_hash(teacher_data["password"].strip())

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
        password=hashed_password
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


def updateTeacherPassword(data: updatePasswordModel, session: Session):
    query = (
        select(Teacher)
        .where(
            Teacher.is_delete == False,
            Teacher.id == data.id
        )
    )

    current_user: Optional[Teacher] = session.exec(query).first()

    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    updatedHashPassword = get_password_hash(data.password)

    current_user.password = updatedHashPassword
    session.add(current_user)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error while updating password."
        )

    return "Password updated successfully"


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

    active_year = getActiveAcademicYear(session)
    if active_year:
        active_year_assignments = session.exec(
            select(TeacherClassHistory).where(
                TeacherClassHistory.teacher_id == id,
                TeacherClassHistory.academic_year_id == active_year.id,
            )
        ).all()
        if active_year_assignments:
            return {
                "id": str(currentTeacher.id),
                "message": "Teacher cannot be deleted while assigned to one or more classes in the active academic year.",
                "subject_affected": 0,
                "lesson_affected": 0,
                "class_affected": len(active_year_assignments),
            }

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
