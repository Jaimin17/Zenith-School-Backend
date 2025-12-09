import uuid
from typing import Optional, List

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlmodel import Session, select, or_
from sqlalchemy import func, Select
from core.config import settings
from models import Student, Teacher, Lesson, Class, Parent, Grade, Result, Attendance
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
    return session.exec(
        select(func.count()).select_from(Student).where(Student.is_delete == False)
    ).first()


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
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE).distinct()
    results = session.exec(query).all()
    return results


def studentSave(student: StudentSave, session: Session):
    username = student.username.strip()
    email = student.email.strip().lower()
    phone = student.phone.strip()

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
        raise HTTPException(status_code=400, detail="Student exists with same username, email, or phone.")

    parent_query = (
        select(Parent)
        .where(Parent.is_delete == False, Parent.id == student.parent_id)
    )

    parent_detail: Optional[Parent] = session.exec(parent_query).first()

    if not parent_detail:
        raise HTTPException(status_code=400, detail="Parent does not exist.")

    class_query = (
        select(Class)
        .where(Class.is_delete == False, Class.id == student.class_id)
    )

    class_detail: Optional[Class] = session.exec(class_query).first()

    if not class_detail:
        raise HTTPException(status_code=400, detail="Class does not exist.")
    else:
        if class_detail.capacity == len(class_detail.students):
            raise HTTPException(status_code=400, detail="Class is already full.")

    grades_query = (
        select(Grade)
        .where(Grade.is_delete == False, Grade.id == student.grade_id)
    )

    grade_detail: Optional[Grade] = session.exec(grades_query).first()

    if not grade_detail:
        raise HTTPException(status_code=400, detail="Grade does not exist.")

    new_student = Student(
        username=username,
        first_name=student.first_name.strip(),
        last_name=student.last_name.strip(),
        email=email,
        phone=phone,
        address=student.address.strip(),
        img=student.img,
        blood_type=student.blood_type,
        sex=student.sex,
        dob=student.dob,
        is_delete=False,
        password="user@123",  # or generate one, depending on your logic
        parent_id=student.parent_id,
        class_id=student.class_id,
        grade_id=student.grade_id
    )

    session.add(new_student)

    try:
        session.flush()  # ensure new_subject.id is generated
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Unique constraint violated (username/email/phone already exists).")

    session.refresh(new_student)

    return {
        "id": str(new_student.id),
        "message": "Student created successfully"
    }


def StudentUpdate(student: StudentUpdateBase, session: Session):
    findStudentQuery = (
        select(Student)
        .where(Student.id == student.id, Student.is_delete == False)
    )

    currentStudent = session.exec(findStudentQuery).first()

    if currentStudent is None:
        raise HTTPException(status_code=404, detail="No student found with the provided ID.")

    new_username = student.username.strip()
    new_email = student.email.strip().lower()
    new_phone = student.phone.strip()

    if not settings.PHONE_RE.match(new_phone):
        raise HTTPException(status_code=400, detail="Invalid Indian phone number. Must be 10 digits starting with 6-9.")

    findSameStudentQuery = (
        select(Student)
        .where(
            or_(
                func.lower(func.trim(Student.username)) == new_username.lower(),
                func.lower(func.trim(Student.email)) == new_email,
                func.trim(Student.phone) == new_phone
            ),
            Student.is_delete == False,
            Student.id != student.id
        )
    )

    existing: Optional[Student] = session.exec(findSameStudentQuery).first()

    if existing:
        raise HTTPException(status_code=400, detail="A student with the same username, email, or phone already exists.")

    # Validate parent_id
    if student.parent_id:
        parent_query = select(Parent).where(Parent.id == student.parent_id, Parent.is_delete == False)
        parent = session.exec(parent_query).first()
        if not parent:
            raise HTTPException(status_code=404, detail=f"No parent found with ID: {student.parent_id}")

    # Validate class_id
    if student.class_id:
        class_query = select(Class).where(Class.id == student.class_id, Class.is_delete == False)
        related_class: Optional[Class] = session.exec(class_query).first()
        if not related_class:
            raise HTTPException(status_code=404, detail=f"No class found with ID: {student.class_id}")
        else:
            if currentStudent.class_id != student.class_id and related_class.capacity == len(related_class.students):
                raise HTTPException(status_code=400, detail=f"Class is already full.")

    # Validate grade_id
    if student.grade_id:
        grade_query = select(Grade).where(Grade.id == student.grade_id, Grade.is_delete == False)
        grade = session.exec(grade_query).first()
        if not grade:
            raise HTTPException(status_code=404, detail=f"No grade found with ID: {student.grade_id}")

    currentStudent.username = new_username
    currentStudent.first_name = student.first_name
    currentStudent.last_name = student.last_name
    currentStudent.email = new_email
    currentStudent.phone = new_phone
    currentStudent.address = student.address.strip()
    currentStudent.img = student.img
    currentStudent.blood_type = student.blood_type
    currentStudent.sex = student.sex
    currentStudent.dob = student.dob
    currentStudent.parent_id = student.parent_id
    currentStudent.class_id = student.class_id
    currentStudent.grade_id = student.grade_id

    session.add(currentStudent)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Unique constraint violated (username/email/phone).")

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
