import uuid
from typing import Optional, List

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlmodel import Session, select, or_
from sqlalchemy import func, Select

from core.FileStorage import process_and_save_image, cleanup_image
from core.config import settings
from models import Student, Teacher, Lesson, Class, Parent, Grade, Result, Attendance, UserSex
from schemas import StudentSave, StudentUpdateBase


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Student.username).like(search_pattern)) |
            (func.lower(Student.first_name).like(search_pattern)) |
            (func.lower(Student.last_name).like(search_pattern))
        )

    return query


def countStudent(session: Session):
    count_boys_query = (
        select(func.count()).select_from(Student).where(
            Student.is_delete == False,
            Student.sex == UserSex.MALE,
        )
    )

    count_boys = session.exec(count_boys_query).first()

    count_girls_query = (
        select(func.count()).select_from(Student).where(
            Student.is_delete == False,
            Student.sex == UserSex.FEMALE,
        )
    )

    count_girls = session.exec(count_girls_query).first()

    return {
        "boys": count_boys,
        "girls": count_girls
    }


def getStudentByIdAndIsDeleteFalse(studentId: uuid.UUID, session: Session):
    query = (
        select(Student)
        .where(Student.id == studentId, Student.is_delete == False)
    )

    studentDetail = session.exec(query).first()
    return studentDetail


def countStudentBySexAll(session: Session):
    query = (
        select(Student.sex, func.count())
        .select_from(Student)
        .where(Student.is_delete == False)
        .group_by(Student.sex)
    )

    results = session.exec(query).all()
    return {sex: count for sex, count in results}


def getAllStudentsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Student)
        .where(Student.is_delete == False)
    )

    query = query.order_by(func.lower(Student.username))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_students = session.exec(query).all()
    return active_students


def getAllStudentsOfTeacherAndIsDeleteFalse(session: Session, teacherId: uuid.UUID, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Student)
        .join(
            Class,
            onclause=(Class.id == Student.class_id)
        )
        .join(
            Lesson,
            onclause=(Lesson.class_id == Class.id)
        )
        .where(
            Lesson.teacher_id == teacherId,
            Student.is_delete == False,
        )
        .distinct()
    )

    query = query.order_by(Student.username)

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    results = session.exec(query).all()
    return results


def getAllStudentsOfParentAndIsDeleteFalse(session: Session, parentId: uuid.UUID, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Student)
        .where(
            Student.parent_id == parentId,
            Student.is_delete == False,
        )
        .distinct()
    )

    query = query.order_by(Student.username)

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    results = session.exec(query).all()
    return results


async def studentSaveWithImage(student_data: dict, img: Optional[UploadFile], session: Session):
    username = student_data["username"].strip()
    email = student_data["email"].strip().lower()
    phone = student_data["phone"].strip()

    if not settings.PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail="Invalid Indian phone number. Must be 10 digits starting with 6-9.")

    duplicate_query = (
        select(Student)
        .where(
            or_(
                func.lower(func.trim(Student.username)) == username.lower(),
                func.lower(func.trim(Student.email)) == email,
                func.trim(Student.phone) == phone
            ),
            Student.is_delete == False
        )
    )

    existing: Optional[Student] = session.exec(duplicate_query).first()

    if existing:
        # Provide more specific error message
        if existing.username.lower() == username.lower():
            raise HTTPException(status_code=400, detail="Username already exists.")
        elif existing.email.lower() == email:
            raise HTTPException(status_code=400, detail="Email already exists.")
        else:
            raise HTTPException(status_code=400, detail="Phone number already exists.")

    parent_query = (
        select(Parent)
        .where(Parent.is_delete == False, Parent.id == student_data["parent_id"])
    )

    parent_detail: Optional[Parent] = session.exec(parent_query).first()

    if not parent_detail:
        raise HTTPException(status_code=404, detail="Parent not found with the provided ID.")

    class_query = (
        select(Class)
        .where(Class.is_delete == False, Class.id == student_data["class_id"])
    )

    class_detail: Optional[Class] = session.exec(class_query).first()

    if not class_detail:
        raise HTTPException(status_code=404, detail="Class not found with the provided ID.")

        # Check class capacity
    current_student_count = len([s for s in class_detail.students if not s.is_delete]) if class_detail.students else 0

    if current_student_count >= class_detail.capacity:
        raise HTTPException(
            status_code=400,
            detail=f"Class is full. Current capacity: {current_student_count}/{class_detail.capacity}"
        )

    grades_query = (
        select(Grade)
        .where(Grade.is_delete == False, Grade.id == student_data["grade_id"])
    )

    grade_detail: Optional[Grade] = session.exec(grades_query).first()

    if not grade_detail:
        raise HTTPException(status_code=404, detail="Grade not found with the provided ID.")

    image_filename = None
    if img and img.filename:
        try:
            image_filename = await process_and_save_image(img, "students", username)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    new_student = Student(
        username=username,
        first_name=student_data["first_name"].strip(),
        last_name=student_data["last_name"].strip(),
        email=email,
        phone=phone,
        address=student_data["address"].strip(),
        img=image_filename,
        blood_type=student_data["blood_type"],
        sex=student_data["sex"],
        dob=student_data["dob"],
        is_delete=False,
        password="user@123",  # or generate one, depending on your logic
        parent_id=student_data["parent_id"],
        class_id=student_data["class_id"],
        grade_id=student_data["grade_id"]
    )

    session.add(new_student)

    try:
        session.flush()  # ensure new_subject.id is generated
        session.commit()
    except IntegrityError as e:
        session.rollback()

        if image_filename:
            image_path = settings.UPLOAD_DIR_DP / "students" / image_filename
            cleanup_image(image_path)
        raise HTTPException(
            status_code=400,
            detail="Database error: Unique constraint violated."
        )

    session.refresh(new_student)

    return {
        "id": str(new_student.id),
        "message": "Student created successfully"
    }


async def StudentUpdate(student_data: dict, img: Optional[UploadFile], session: Session):
    file_name = img
    print(file_name)

    findStudentQuery = (
        select(Student)
        .where(Student.id == student_data["id"], Student.is_delete == False)
    )

    currentStudent = session.exec(findStudentQuery).first()

    if currentStudent is None:
        raise HTTPException(status_code=404, detail="No student found with the provided ID.")

    new_username = student_data["username"].strip()
    new_email = student_data["email"].strip().lower()
    new_phone = student_data["phone"].strip()

    findSameStudentQuery = (
        select(Student)
        .where(
            or_(
                func.lower(func.trim(Student.username)) == new_username.lower(),
                func.lower(func.trim(Student.email)) == new_email,
                func.trim(Student.phone) == new_phone
            ),
            Student.is_delete == False,
            Student.id != student_data["id"]
        )
    )

    existing: Optional[Student] = session.exec(findSameStudentQuery).first()

    if existing:
        # Determine which field is duplicated
        if existing.username.lower() == new_username.lower():
            raise HTTPException(
                status_code=409,
                detail="A student with this username already exists."
            )
        elif existing.email.lower() == new_email:
            raise HTTPException(
                status_code=409,
                detail="A student with this email already exists."
            )
        else:
            raise HTTPException(
                status_code=409,
                detail="A student with this phone number already exists."
            )

    # Validate parent_id
    parent_query = select(Parent).where(
        Parent.id == student_data["parent_id"],
        Parent.is_delete == False
    )
    parent = session.exec(parent_query).first()
    if not parent:
        raise HTTPException(
            status_code=404,
            detail=f"No parent found with ID: {student_data['parent_id']}"
        )

    # Validate class_id
    class_query = select(Class).where(
        Class.id == student_data["class_id"],
        Class.is_delete == False
    )
    related_class: Optional[Class] = session.exec(class_query).first()
    if not related_class:
        raise HTTPException(
            status_code=404,
            detail=f"No class found with ID: {student_data['class_id']}"
        )

    if currentStudent.class_id != student_data["class_id"]:
        # Count current students in the target class (excluding soft-deleted)
        current_students_count = len([s for s in related_class.students if not s.is_delete])

        if current_students_count >= related_class.capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Class '{related_class.name}' is already full (capacity: {related_class.capacity})."
            )

    # Validate grade_id
    grade_query = select(Grade).where(
        Grade.id == student_data["grade_id"],
        Grade.is_delete == False
    )
    grade = session.exec(grade_query).first()
    if not grade:
        raise HTTPException(
            status_code=404,
            detail=f"No grade found with ID: {student_data['grade_id']}"
        )

    image_filename = currentStudent.img
    if img and img.filename:
        try:
            image_filename = await process_and_save_image(img, "students", new_username)

            if currentStudent.img and currentStudent.img != image_filename:
                old_image_path = settings.UPLOAD_DIR_DP / "students" / currentStudent.img
                cleanup_image(old_image_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

    currentStudent.username = new_username
    currentStudent.first_name = student_data["first_name"]
    currentStudent.last_name = student_data["last_name"]
    currentStudent.email = new_email
    currentStudent.phone = new_phone
    currentStudent.address = student_data["address"]
    currentStudent.img = image_filename
    currentStudent.blood_type = student_data["blood_type"]
    currentStudent.sex = student_data["sex"]
    currentStudent.dob = student_data["dob"]
    currentStudent.parent_id = student_data["parent_id"]
    currentStudent.class_id = student_data["class_id"]
    currentStudent.grade_id = student_data["grade_id"]

    session.add(currentStudent)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if img and img.filename and image_filename != currentStudent.img:
            new_image_path = settings.UPLOAD_DIR_DP / "students" / image_filename
            cleanup_image(new_image_path)

        raise HTTPException(
            status_code=409,
            detail="Database integrity error: Username, email, or phone already exists."
        )

    session.refresh(currentStudent)

    return {
        "id": str(currentStudent.id),
        "message": "Student updated successfully"
    }


def studentSoftDelete(id: uuid.UUID, session: Session):
    findStudent = (
        select(Student)
        .where(Student.id == id, Student.is_delete == False)
    )

    currentStudent: Optional[Student] = session.exec(findStudent).first()

    if currentStudent is None:
        raise HTTPException(status_code=404, detail="No student found with the provided ID.")

    parent_removed = 1 if currentStudent.parent_id is not None else 0
    class_removed = 1 if currentStudent.class_id is not None else 0
    grade_removed = 1 if currentStudent.grade_id is not None else 0

    currentStudent.parent_id = None
    currentStudent.class_id = None
    currentStudent.grade_id = None

    attendance_query = (
        select(Attendance)
        .where(Attendance.student_id == id, Attendance.is_delete == False)
    )
    attendances: List[Attendance] = session.exec(attendance_query).all()
    attendance_count = 0
    for attendance in attendances:
        attendance.is_delete = True
        session.add(attendance)
        attendance_count += 1

    result_query = (
        select(Result)
        .where(Result.student_id == id, Result.is_delete == False)
    )
    results: List[Result] = session.exec(result_query).all()
    result_count = 0
    for result in results:
        result.is_delete = True
        session.add(result)
        result_count += 1

    # Soft delete the student
    currentStudent.is_delete = True
    session.add(currentStudent)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Error deleting student and related records.")

    # Refresh to get latest relationships (optional)
    session.refresh(currentStudent)

    return {
        "id": str(currentStudent.id),
        "message": "Student deleted successfully.",
        "parent_removed": parent_removed,
        "class_removed": class_removed,
        "grade_removed": grade_removed,
        "attendance_affected": attendance_count,
        "result_affected": result_count
    }
