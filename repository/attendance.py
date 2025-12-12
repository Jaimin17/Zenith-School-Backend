import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import func
from sqlmodel import Session, select

from models import Attendance, Lesson, Student
from schemas import AttendanceBulkSave, AttendanceSave, AttendanceUpdate, AttendanceDetail


def attendanceOfWeek(session: Session, monday: datetime, sunday: datetime):
    query = (
        select(Attendance)
        .where(
            Attendance.attendance_date >= monday,
            Attendance.attendance_date <= sunday,
            Attendance.is_delete == False
        )
    )

    query = query.order_by(Attendance.attendance_date.desc())

    attendance = session.exec(query).all()
    return attendance


def attendanceOfStudentOfCurrentYear(studentId: uuid.UUID, startDate: date, session: Session):
    query = (
        select(Attendance)
        .where(Attendance.attendance_date >= startDate, Attendance.student_id == studentId,
               Attendance.is_delete == False)
    )

    query = query.order_by(Attendance.attendance_date.desc())

    attendance = session.exec(query).all()
    return attendance


def attendanceBulkSave(bulk_data: AttendanceBulkSave, userId: uuid.UUID, role: str, session: Session):
    lesson_query = (
        select(Lesson)
        .where(Lesson.id == bulk_data.lesson_id, Lesson.is_delete == False)
    )
    lesson = session.exec(lesson_query).first()
    if not lesson:
        raise HTTPException(
            status_code=404,
            detail=f"No active lesson found with ID: {bulk_data.lesson_id}"
        )

    if not lesson.class_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson is not associated with any class."
        )

    if role == "teacher":
        if lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to mark attendance for this lesson."
            )

    students_query = (
        select(Student)
        .where(Student.class_id == lesson.class_id, Student.is_delete == False)
    )
    valid_students = session.exec(students_query).all()
    valid_student_ids = {student.id for student in valid_students}

    provided_student_ids = {record.student_id for record in bulk_data.attendances}
    invalid_students = provided_student_ids - valid_student_ids

    if invalid_students:
        raise HTTPException(
            status_code=400,
            detail=f"The following student IDs do not belong to this lesson's class: {', '.join(str(sid) for sid in invalid_students)}"
        )

    if len(provided_student_ids) != len(bulk_data.attendances):
        raise HTTPException(
            status_code=400,
            detail="Duplicate student IDs found in the attendance list."
        )

    existing_query = (
        select(Attendance)
        .where(
            Attendance.lesson_id == bulk_data.lesson_id,
            func.date(Attendance.attendance_date) == bulk_data.attendance_date,
            Attendance.student_id.in_(provided_student_ids),
            Attendance.is_delete == False
        )
    )
    existing_attendances = session.exec(existing_query).all()

    if existing_attendances:
        existing_student_ids = [str(att.student_id) for att in existing_attendances]
        raise HTTPException(
            status_code=409,
            detail=f"Attendance already exists for students: {', '.join(existing_student_ids)} on {bulk_data.attendance_date}"
        )

    new_attendances = []
    saved_count = 0
    failed_records = []

    for record in bulk_data.attendances:
        try:
            attendance_datetime = datetime.combine(
                bulk_data.attendance_date,
                datetime.now().time()
            )

            new_attendance = Attendance(
                student_id=record.student_id,
                lesson_id=bulk_data.lesson_id,
                attendance_date=attendance_datetime,
                present=record.present,
                is_delete=False
            )
            new_attendances.append(new_attendance)
            session.add(new_attendance)
            saved_count += 1
        except Exception as e:
            failed_records.append({
                "student_id": str(record.student_id),
                "error": str(e)
            })

    if failed_records:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save some attendance records: {failed_records}"
        )

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Database integrity error while saving attendance records."
        )

    return {
        "message": "Attendance saved successfully for all students.",
        "total_saved": saved_count,
        "failed": failed_records
    }


def attendanceSave(attendance_data: AttendanceSave, userId: uuid.UUID, role: str, session: Session):
    lesson_query = select(Lesson).where(
        Lesson.id == attendance_data.lesson_id,
        Lesson.is_delete == False
    )
    lesson = session.exec(lesson_query).first()
    if not lesson:
        raise HTTPException(
            status_code=404,
            detail=f"No active lesson found with ID: {attendance_data.lesson_id}"
        )

    if not lesson.class_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson is not associated with any class."
        )

    if role == "teacher":
        if lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to mark attendance for this lesson."
            )

    student_query = select(Student).where(
        Student.id == attendance_data.student_id,
        Student.is_delete == False
    )
    student = session.exec(student_query).first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail=f"No active student found with ID: {attendance_data.student_id}"
        )

    if student.class_id != lesson.class_id:
        raise HTTPException(
            status_code=400,
            detail="Student does not belong to the class associated with this lesson."
        )

    duplicate_query = select(Attendance).where(
        Attendance.lesson_id == attendance_data.lesson_id,
        Attendance.student_id == attendance_data.student_id,
        func.date(Attendance.attendance_date) == attendance_data.attendance_date,
        Attendance.is_delete == False
    )
    existing = session.exec(duplicate_query).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Attendance already exists for this student on {attendance_data.attendance_date}"
        )

    attendance_datetime = datetime.combine(
        attendance_data.attendance_date,
        datetime.now().time()
    )

    # Create new attendance record
    new_attendance = Attendance(
        student_id=attendance_data.student_id,
        lesson_id=attendance_data.lesson_id,
        attendance_date=attendance_datetime,
        present=attendance_data.present,
        is_delete=False
    )

    session.add(new_attendance)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Attendance already exists (unique constraint violation)."
        )

    session.refresh(new_attendance)

    return {
        "id": str(new_attendance.id),
        "message": "Attendance saved successfully"
    }


def attendanceUpdate(attendance_data: AttendanceUpdate, userId: uuid.UUID, role: str, session: Session):
    attendance_query = select(Attendance).where(
        Attendance.id == attendance_data.id,
        Attendance.is_delete == False
    )
    current_attendance = session.exec(attendance_query).first()
    if not current_attendance:
        raise HTTPException(
            status_code=404,
            detail=f"No active attendance found with ID: {attendance_data.id}"
        )

    if role == "teacher":
        if not current_attendance.lesson:
            raise HTTPException(
                status_code=404,
                detail="Attendance is not associated with any lesson."
            )
        if current_attendance.lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to update this attendance record."
            )

    current_attendance.present = attendance_data.present
    session.add(current_attendance)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error updating attendance record."
        )

    session.refresh(current_attendance)

    return {
        "id": str(current_attendance.id),
        "message": "Attendance updated successfully"
    }


def attendanceSoftDelete(id: uuid.UUID, userId: uuid.UUID, role: str, session: Session):
    attendance_query = select(Attendance).where(
        Attendance.id == id,
        Attendance.is_delete == False
    )
    current_attendance = session.exec(attendance_query).first()
    if not current_attendance:
        raise HTTPException(
            status_code=404,
            detail=f"No active attendance found with ID: {id}"
        )

    if role == "teacher":
        if not current_attendance.lesson:
            raise HTTPException(
                status_code=404,
                detail="Attendance is not associated with any lesson."
            )
        if current_attendance.lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to delete this attendance record."
            )

    current_attendance.is_delete = True
    session.add(current_attendance)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error deleting attendance record."
        )

    session.refresh(current_attendance)

    return {
        "id": str(current_attendance.id),
        "message": "Attendance deleted successfully."
    }


def getAttendanceByLesson(lesson_id: uuid.UUID, attendance_date: Optional[date], userId: uuid.UUID, role: str,
                          session: Session):
    lesson_query = select(Lesson).where(
        Lesson.id == lesson_id,
        Lesson.is_delete == False
    )
    lesson = session.exec(lesson_query).first()
    if not lesson:
        raise HTTPException(
            status_code=404,
            detail=f"No active lesson found with ID: {lesson_id}"
        )

    if role == "teacher":
        if lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view attendance for this lesson."
            )

    attendance_query = (
        select(Attendance, Student, Lesson)
        .join(Student, Attendance.student_id == Student.id)
        .join(Lesson, Attendance.lesson_id == Lesson.id)
        .where(
            Attendance.lesson_id == lesson_id,
            Attendance.is_delete == False,
            Student.is_delete == False
        )
    )

    if attendance_date:
        attendance_query = attendance_query.where(
            func.date(Attendance.attendance_date) == attendance_date
        )

    attendance_query = attendance_query.order_by(Attendance.attendance_date.desc())

    results = session.exec(attendance_query).all()

    attendance_list = []
    for attendance, student, lesson in results:
        attendance_list.append(AttendanceDetail(
            id=attendance.id,
            student_id=student.id,
            student_name=f"{student.first_name} {student.last_name}",
            lesson_id=lesson.id,
            lesson_name=lesson.name,
            attendance_date=attendance.attendance_date.date(),
            present=attendance.present,
            is_delete=attendance.is_delete
        ))

    return {
        "attendances": attendance_list,
        "total": len(attendance_list)
    }
