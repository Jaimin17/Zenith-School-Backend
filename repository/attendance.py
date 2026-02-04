import uuid
from datetime import datetime, date
from typing import Optional
from calendar import monthrange

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import func, case, and_, distinct
from sqlmodel import Session, select

from models import Attendance, Lesson, Student, Class, Subject, Teacher, Day
from schemas import (
    AttendanceBulkSave, AttendanceSave, AttendanceUpdate, AttendanceDetail,
    AttendanceDashboardSummary, ClassAttendanceSummary, ClasswiseAttendanceResponse,
    StudentMonthlyAttendance, StudentAttendanceRecord, CalendarDayData,
    CalendarHeatmapResponse, ClassStudentAttendance, ClassAttendanceDetailResponse,
    TeacherClassSummary, StudentRosterItem, LessonRosterResponse, LessonForDateItem,
    LessonsForDateResponse, AttendanceTakeRequest, AttendanceTakeResponse
)


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


# ===================== Dashboard & Summary Functions =====================

def getDashboardSummary(target_date: date, session: Session) -> AttendanceDashboardSummary:
    """
    Get admin dashboard summary for a specific date.
    Returns: total classes, classes with attendance, pending, present/absent counts, rate
    """
    # Get all active classes
    total_classes_query = select(func.count(Class.id)).where(Class.is_delete == False)
    total_classes = session.exec(total_classes_query).first() or 0

    # Get total students
    total_students_query = select(func.count(Student.id)).where(Student.is_delete == False)
    total_students = session.exec(total_students_query).first() or 0

    # Get attendance records for the specific date
    attendance_query = (
        select(
            func.count(Attendance.id).label('total'),
            func.sum(case((Attendance.present == True, 1), else_=0)).label('present'),
            func.sum(case((Attendance.present == False, 1), else_=0)).label('absent')
        )
        .where(
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False
        )
    )
    attendance_stats = session.exec(attendance_query).first()

    present_count = int(attendance_stats[1] or 0)
    absent_count = int(attendance_stats[2] or 0)
    total_attendance = present_count + absent_count

    # Get classes that have attendance recorded for this date
    classes_with_attendance_query = (
        select(func.count(distinct(Lesson.class_id)))
        .join(Attendance, Attendance.lesson_id == Lesson.id)
        .where(
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False,
            Lesson.is_delete == False
        )
    )
    classes_with_attendance = session.exec(classes_with_attendance_query).first() or 0

    pending_classes = total_classes - classes_with_attendance
    attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0.0

    return AttendanceDashboardSummary(
        date=target_date,
        total_classes=total_classes,
        classes_with_attendance=classes_with_attendance,
        pending_classes=pending_classes,
        total_students=total_students,
        present_count=present_count,
        absent_count=absent_count,
        attendance_rate=round(attendance_rate, 2)
    )


def getClasswiseSummary(target_date: date, session: Session) -> ClasswiseAttendanceResponse:
    """
    Get class-wise attendance summary for a specific date.
    Returns list of classes with their attendance stats.
    """
    # Get all active classes with their student counts
    classes_query = (
        select(Class)
        .where(Class.is_delete == False)
        .order_by(Class.name)
    )
    classes = session.exec(classes_query).all()

    class_summaries = []

    for cls in classes:
        # Count students in this class
        student_count_query = (
            select(func.count(Student.id))
            .where(Student.class_id == cls.id, Student.is_delete == False)
        )
        total_students = session.exec(student_count_query).first() or 0

        # Get attendance for this class on this date
        attendance_query = (
            select(
                func.count(Attendance.id).label('total'),
                func.sum(case((Attendance.present == True, 1), else_=0)).label('present'),
                func.sum(case((Attendance.present == False, 1), else_=0)).label('absent')
            )
            .join(Lesson, Attendance.lesson_id == Lesson.id)
            .where(
                Lesson.class_id == cls.id,
                func.date(Attendance.attendance_date) == target_date,
                Attendance.is_delete == False,
                Lesson.is_delete == False
            )
        )
        attendance_stats = session.exec(attendance_query).first()

        present_count = int(attendance_stats[1] or 0)
        absent_count = int(attendance_stats[2] or 0)
        marked_count = present_count + absent_count
        not_marked_count = max(0, total_students - marked_count)

        has_attendance = marked_count > 0
        attendance_rate = (present_count / marked_count * 100) if marked_count > 0 else 0.0

        # Get grade level if available
        grade_level = cls.grade.level if cls.grade else None

        class_summaries.append(ClassAttendanceSummary(
            class_id=cls.id,
            class_name=cls.name,
            grade_level=grade_level,
            total_students=total_students,
            present_count=present_count,
            absent_count=absent_count,
            not_marked_count=not_marked_count,
            attendance_rate=round(attendance_rate, 2),
            has_attendance=has_attendance
        ))

    return ClasswiseAttendanceResponse(
        date=target_date,
        classes=class_summaries,
        total_classes=len(class_summaries)
    )


def getClassAttendanceDetail(
    class_id: uuid.UUID,
    target_date: date,
    session: Session
) -> ClassAttendanceDetailResponse:
    """
    Get detailed attendance for a specific class on a specific date.
    Returns all students with their attendance status.
    """
    # Verify class exists
    class_query = select(Class).where(Class.id == class_id, Class.is_delete == False)
    cls = session.exec(class_query).first()
    if not cls:
        raise HTTPException(status_code=404, detail=f"Class not found with ID: {class_id}")

    # Get all students in this class
    students_query = (
        select(Student)
        .where(Student.class_id == class_id, Student.is_delete == False)
        .order_by(Student.first_name, Student.last_name)
    )
    students = session.exec(students_query).all()

    # Get attendance records for this class on this date
    attendance_query = (
        select(Attendance, Lesson)
        .join(Lesson, Attendance.lesson_id == Lesson.id)
        .where(
            Lesson.class_id == class_id,
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False,
            Lesson.is_delete == False
        )
    )
    attendance_results = session.exec(attendance_query).all()

    # Build attendance map by student_id
    attendance_map = {}
    lesson_info = None
    for attendance, lesson in attendance_results:
        attendance_map[attendance.student_id] = attendance
        if not lesson_info:
            lesson_info = lesson

    # Build student attendance list
    student_attendances = []
    present_count = 0
    absent_count = 0
    not_marked_count = 0

    for student in students:
        attendance = attendance_map.get(student.id)
        if attendance:
            if attendance.present:
                present_count += 1
            else:
                absent_count += 1
            student_attendances.append(ClassStudentAttendance(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                username=student.username,
                attendance_id=attendance.id,
                present=attendance.present,
                marked_at=attendance.attendance_date
            ))
        else:
            not_marked_count += 1
            student_attendances.append(ClassStudentAttendance(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                username=student.username,
                attendance_id=None,
                present=None,
                marked_at=None
            ))

    return ClassAttendanceDetailResponse(
        class_id=cls.id,
        class_name=cls.name,
        date=target_date,
        lesson_id=lesson_info.id if lesson_info else None,
        lesson_name=lesson_info.name if lesson_info else None,
        total_students=len(students),
        present_count=present_count,
        absent_count=absent_count,
        not_marked_count=not_marked_count,
        students=student_attendances
    )


def getStudentMonthlyAttendance(
    student_id: uuid.UUID,
    year: int,
    month: int,
    session: Session
) -> StudentMonthlyAttendance:
    """
    Get monthly attendance for a specific student.
    Returns daily records and summary stats.
    """
    # Verify student exists
    student_query = select(Student).where(Student.id == student_id, Student.is_delete == False)
    student = session.exec(student_query).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found with ID: {student_id}")

    # Calculate date range for the month
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    # Get all attendance records for this student in this month
    attendance_query = (
        select(Attendance, Lesson, Subject)
        .join(Lesson, Attendance.lesson_id == Lesson.id)
        .outerjoin(Subject, Lesson.subject_id == Subject.id)
        .where(
            Attendance.student_id == student_id,
            func.date(Attendance.attendance_date) >= start_date,
            func.date(Attendance.attendance_date) <= end_date,
            Attendance.is_delete == False,
            Lesson.is_delete == False
        )
        .order_by(Attendance.attendance_date.desc())
    )
    results = session.exec(attendance_query).all()

    records = []
    present_days = 0
    absent_days = 0

    for attendance, lesson, subject in results:
        if attendance.present:
            present_days += 1
        else:
            absent_days += 1

        records.append(StudentAttendanceRecord(
            id=attendance.id,
            date=attendance.attendance_date.date(),
            present=attendance.present,
            lesson_id=lesson.id,
            lesson_name=lesson.name,
            subject_name=subject.name if subject else None
        ))

    total_days = present_days + absent_days
    attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0.0

    return StudentMonthlyAttendance(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        month=month,
        year=year,
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        attendance_rate=round(attendance_rate, 2),
        records=records
    )


def getCalendarHeatmap(
    student_id: uuid.UUID,
    year: int,
    month: int,
    session: Session
) -> CalendarHeatmapResponse:
    """
    Get calendar heatmap data for a student's attendance.
    Returns daily attendance rates for visualization.
    """
    # Verify student exists
    student_query = select(Student).where(Student.id == student_id, Student.is_delete == False)
    student = session.exec(student_query).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found with ID: {student_id}")

    # Calculate date range for the month
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    # Get attendance grouped by date
    attendance_query = (
        select(
            func.date(Attendance.attendance_date).label('att_date'),
            func.count(Attendance.id).label('total'),
            func.sum(case((Attendance.present == True, 1), else_=0)).label('present'),
            func.sum(case((Attendance.present == False, 1), else_=0)).label('absent')
        )
        .where(
            Attendance.student_id == student_id,
            func.date(Attendance.attendance_date) >= start_date,
            func.date(Attendance.attendance_date) <= end_date,
            Attendance.is_delete == False
        )
        .group_by(func.date(Attendance.attendance_date))
        .order_by(func.date(Attendance.attendance_date))
    )
    results = session.exec(attendance_query).all()

    # Build daily data
    days_data = []
    total_present = 0
    total_absent = 0

    for row in results:
        att_date = row[0]
        total = int(row[1] or 0)
        present = int(row[2] or 0)
        absent = int(row[3] or 0)

        total_present += present
        total_absent += absent

        rate = (present / total * 100) if total > 0 else 0.0

        days_data.append(CalendarDayData(
            date=att_date,
            present_count=present,
            absent_count=absent,
            total_records=total,
            attendance_rate=round(rate, 2)
        ))

    total_records = total_present + total_absent
    monthly_rate = (total_present / total_records * 100) if total_records > 0 else 0.0

    return CalendarHeatmapResponse(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        month=month,
        year=year,
        days=days_data,
        monthly_summary={
            "total_days": total_records,
            "present_days": total_present,
            "absent_days": total_absent,
            "attendance_rate": round(monthly_rate, 2)
        }
    )


def getTeacherClasses(
    teacher_id: uuid.UUID,
    target_date: date,
    session: Session
) -> list[TeacherClassSummary]:
    """
    Get classes assigned to a teacher with attendance status for a specific date.
    """
    # Get lessons taught by this teacher
    lessons_query = (
        select(Lesson, Class, Subject)
        .join(Class, Lesson.class_id == Class.id)
        .outerjoin(Subject, Lesson.subject_id == Subject.id)
        .where(
            Lesson.teacher_id == teacher_id,
            Lesson.is_delete == False,
            Class.is_delete == False
        )
        .order_by(Class.name, Lesson.name)
    )
    lessons = session.exec(lessons_query).all()

    summaries = []
    for lesson, cls, subject in lessons:
        # Count students in this class
        student_count_query = (
            select(func.count(Student.id))
            .where(Student.class_id == cls.id, Student.is_delete == False)
        )
        total_students = session.exec(student_count_query).first() or 0

        # Check if attendance is marked for this lesson today
        attendance_query = (
            select(
                func.count(Attendance.id).label('total'),
                func.sum(case((Attendance.present == True, 1), else_=0)).label('present'),
                func.sum(case((Attendance.present == False, 1), else_=0)).label('absent')
            )
            .where(
                Attendance.lesson_id == lesson.id,
                func.date(Attendance.attendance_date) == target_date,
                Attendance.is_delete == False
            )
        )
        attendance_stats = session.exec(attendance_query).first()

        present_count = int(attendance_stats[1] or 0)
        absent_count = int(attendance_stats[2] or 0)
        attendance_marked = (present_count + absent_count) > 0

        summaries.append(TeacherClassSummary(
            class_id=cls.id,
            class_name=cls.name,
            lesson_id=lesson.id,
            lesson_name=lesson.name,
            subject_name=subject.name if subject else None,
            day=lesson.day.value if lesson.day else "",
            total_students=total_students,
            attendance_marked=attendance_marked,
            present_count=present_count,
            absent_count=absent_count
        ))

    return summaries


def getParentChildrenAttendance(
    parent_id: uuid.UUID,
    year: int,
    month: int,
    session: Session
) -> list[StudentMonthlyAttendance]:
    """
    Get monthly attendance for all children of a parent.
    """
    # Get all children of this parent
    children_query = (
        select(Student)
        .where(Student.parent_id == parent_id, Student.is_delete == False)
    )
    children = session.exec(children_query).all()

    if not children:
        raise HTTPException(status_code=404, detail="No children found for this parent")

    results = []
    for child in children:
        monthly_attendance = getStudentMonthlyAttendance(child.id, year, month, session)
        results.append(monthly_attendance)

    return results


# ===================== Take Attendance Workflow Functions =====================

def getLessonRoster(
    lesson_id: uuid.UUID,
    target_date: date,
    user_id: uuid.UUID,
    role: str,
    session: Session
) -> LessonRosterResponse:
    """
    Get the student roster for a lesson to take attendance.
    Returns all students in the class with their existing attendance status (if any).
    """
    # Verify lesson exists
    lesson_query = (
        select(Lesson, Class, Subject)
        .join(Class, Lesson.class_id == Class.id)
        .outerjoin(Subject, Lesson.subject_id == Subject.id)
        .where(Lesson.id == lesson_id, Lesson.is_delete == False)
    )
    result = session.exec(lesson_query).first()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Lesson not found with ID: {lesson_id}")
    
    lesson, cls, subject = result
    
    # Authorization check for teachers
    if role == "teacher" and lesson.teacher_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to take attendance for this lesson."
        )
    
    # Get all students in this class
    students_query = (
        select(Student)
        .where(Student.class_id == cls.id, Student.is_delete == False)
        .order_by(Student.first_name, Student.last_name)
    )
    students = session.exec(students_query).all()
    
    # Get existing attendance for this lesson on this date
    attendance_query = (
        select(Attendance)
        .where(
            Attendance.lesson_id == lesson_id,
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False
        )
    )
    existing_attendance = session.exec(attendance_query).all()
    
    # Build attendance map
    attendance_map = {att.student_id: att for att in existing_attendance}
    
    # Build roster
    roster_items = []
    marked_count = 0
    
    for student in students:
        att = attendance_map.get(student.id)
        if att:
            marked_count += 1
            roster_items.append(StudentRosterItem(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                username=student.username,
                img=student.img,
                attendance_id=att.id,
                present=att.present
            ))
        else:
            roster_items.append(StudentRosterItem(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                username=student.username,
                img=student.img,
                attendance_id=None,
                present=None
            ))
    
    return LessonRosterResponse(
        lesson_id=lesson.id,
        lesson_name=lesson.name,
        class_id=cls.id,
        class_name=cls.name,
        subject_name=subject.name if subject else None,
        target_date=target_date,
        total_students=len(students),
        attendance_exists=marked_count > 0,
        marked_count=marked_count,
        students=roster_items
    )


def getLessonsForDate(
    target_date: date,
    class_id: Optional[uuid.UUID],
    user_id: uuid.UUID,
    role: str,
    session: Session
) -> LessonsForDateResponse:
    """
    Get lessons for a specific date, optionally filtered by class.
    For teachers, only shows their assigned lessons.
    """
    # Get day of week from date
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_of_week = day_names[target_date.weekday()]
    
    # Map to Day enum
    day_enum_map = {
        "Monday": Day.MONDAY,
        "Tuesday": Day.TUESDAY,
        "Wednesday": Day.WEDNESDAY,
        "Thursday": Day.THURSDAY,
        "Friday": Day.FRIDAY,
        "Saturday": Day.SATURDAY,
    }
    
    # If it's Sunday, no lessons
    if day_of_week == "Sunday":
        return LessonsForDateResponse(
            date=target_date,
            day_of_week=day_of_week,
            total_lessons=0,
            lessons=[]
        )
    
    day_enum = day_enum_map.get(day_of_week)
    
    # Build query
    lessons_query = (
        select(Lesson, Class, Subject, Teacher)
        .join(Class, Lesson.class_id == Class.id)
        .outerjoin(Subject, Lesson.subject_id == Subject.id)
        .outerjoin(Teacher, Lesson.teacher_id == Teacher.id)
        .where(
            Lesson.day == day_enum,
            Lesson.is_delete == False,
            Class.is_delete == False
        )
    )
    
    # Filter by class if provided
    if class_id:
        lessons_query = lessons_query.where(Lesson.class_id == class_id)
    
    # Filter by teacher if role is teacher
    if role == "teacher":
        lessons_query = lessons_query.where(Lesson.teacher_id == user_id)
    
    lessons_query = lessons_query.order_by(Class.name, Lesson.start_time)
    
    results = session.exec(lessons_query).all()
    
    lesson_items = []
    for lesson, cls, subject, teacher in results:
        # Count students in this class
        student_count_query = (
            select(func.count(Student.id))
            .where(Student.class_id == cls.id, Student.is_delete == False)
        )
        students_count = session.exec(student_count_query).first() or 0
        
        # Get attendance status for this lesson on this date
        attendance_query = (
            select(
                func.count(Attendance.id).label('total'),
                func.sum(case((Attendance.present == True, 1), else_=0)).label('present'),
                func.sum(case((Attendance.present == False, 1), else_=0)).label('absent')
            )
            .where(
                Attendance.lesson_id == lesson.id,
                func.date(Attendance.attendance_date) == target_date,
                Attendance.is_delete == False
            )
        )
        att_stats = session.exec(attendance_query).first()
        
        present_count = int(att_stats[1] or 0)
        absent_count = int(att_stats[2] or 0)
        marked_count = present_count + absent_count
        
        # Determine attendance status
        if marked_count == 0:
            attendance_status = "not_taken"
        elif marked_count < students_count:
            attendance_status = "partial"
        else:
            attendance_status = "complete"
        
        lesson_items.append(LessonForDateItem(
            lesson_id=lesson.id,
            lesson_name=lesson.name,
            class_id=cls.id,
            class_name=cls.name,
            subject_id=subject.id if subject else None,
            subject_name=subject.name if subject else None,
            teacher_id=teacher.id if teacher else None,
            teacher_name=f"{teacher.first_name} {teacher.last_name}" if teacher else None,
            start_time=lesson.start_time,
            end_time=lesson.end_time,
            day=lesson.day.value if lesson.day else day_of_week,
            attendance_status=attendance_status,
            students_count=students_count,
            present_count=present_count,
            absent_count=absent_count
        ))
    
    return LessonsForDateResponse(
        date=target_date,
        day_of_week=day_of_week,
        total_lessons=len(lesson_items),
        lessons=lesson_items
    )


def takeAttendance(
    request: AttendanceTakeRequest,
    user_id: uuid.UUID,
    role: str,
    session: Session
) -> AttendanceTakeResponse:
    """
    Take or update attendance for a lesson.
    Supports both creating new records and updating existing ones.
    """
    # Verify lesson exists
    lesson_query = select(Lesson).where(Lesson.id == request.lesson_id, Lesson.is_delete == False)
    lesson = session.exec(lesson_query).first()
    
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found with ID: {request.lesson_id}")
    
    if not lesson.class_id:
        raise HTTPException(status_code=400, detail="Lesson is not associated with any class.")
    
    # Authorization check for teachers
    if role == "teacher" and lesson.teacher_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to take attendance for this lesson."
        )
    
    # Validate all students belong to the class
    students_query = (
        select(Student)
        .where(Student.class_id == lesson.class_id, Student.is_delete == False)
    )
    valid_students = session.exec(students_query).all()
    valid_student_ids = {student.id for student in valid_students}
    
    provided_student_ids = {record.student_id for record in request.records}
    invalid_students = provided_student_ids - valid_student_ids
    
    if invalid_students:
        raise HTTPException(
            status_code=400,
            detail=f"The following student IDs do not belong to this lesson's class: {', '.join(str(sid) for sid in invalid_students)}"
        )
    
    # Check for duplicate student IDs in request
    if len(provided_student_ids) != len(request.records):
        raise HTTPException(
            status_code=400,
            detail="Duplicate student IDs found in the attendance records."
        )
    
    # Get existing attendance records for this lesson on this date
    existing_query = (
        select(Attendance)
        .where(
            Attendance.lesson_id == request.lesson_id,
            func.date(Attendance.attendance_date) == request.attendance_date,
            Attendance.student_id.in_(provided_student_ids),
            Attendance.is_delete == False
        )
    )
    existing_attendance = session.exec(existing_query).all()
    existing_map = {att.student_id: att for att in existing_attendance}
    
    # If attendance exists and overwrite is not allowed
    if existing_attendance and not request.overwrite_existing:
        existing_student_ids = [str(att.student_id) for att in existing_attendance]
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Attendance already exists for {len(existing_attendance)} students on {request.attendance_date}",
                "existing_students": existing_student_ids,
                "hint": "Set 'overwrite_existing: true' to update existing records"
            }
        )
    
    # Process attendance records
    created_count = 0
    updated_count = 0
    present_count = 0
    absent_count = 0
    
    attendance_datetime = datetime.combine(
        request.attendance_date,
        datetime.now().time()
    )
    
    for record in request.records:
        if record.present:
            present_count += 1
        else:
            absent_count += 1
        
        existing_att = existing_map.get(record.student_id)
        
        if existing_att:
            # Update existing record
            existing_att.present = record.present
            existing_att.attendance_date = attendance_datetime
            session.add(existing_att)
            updated_count += 1
        else:
            # Create new record
            new_attendance = Attendance(
                student_id=record.student_id,
                lesson_id=request.lesson_id,
                attendance_date=attendance_datetime,
                present=record.present,
                is_delete=False
            )
            session.add(new_attendance)
            created_count += 1
    
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error while saving attendance records."
        )
    
    return AttendanceTakeResponse(
        message="Attendance saved successfully",
        lesson_id=request.lesson_id,
        attendance_date=request.attendance_date,
        total_students=len(request.records),
        created_count=created_count,
        updated_count=updated_count,
        present_count=present_count,
        absent_count=absent_count
    )


def checkAttendanceExists(
    lesson_id: uuid.UUID,
    target_date: date,
    session: Session
) -> dict:
    """
    Check if attendance has been taken for a lesson on a specific date.
    Returns summary of existing attendance.
    """
    # Verify lesson exists
    lesson_query = (
        select(Lesson, Class)
        .join(Class, Lesson.class_id == Class.id)
        .where(Lesson.id == lesson_id, Lesson.is_delete == False)
    )
    result = session.exec(lesson_query).first()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Lesson not found with ID: {lesson_id}")
    
    lesson, cls = result
    
    # Count students in class
    student_count_query = (
        select(func.count(Student.id))
        .where(Student.class_id == cls.id, Student.is_delete == False)
    )
    total_students = session.exec(student_count_query).first() or 0
    
    # Get attendance stats
    attendance_query = (
        select(
            func.count(Attendance.id).label('total'),
            func.sum(case((Attendance.present == True, 1), else_=0)).label('present'),
            func.sum(case((Attendance.present == False, 1), else_=0)).label('absent')
        )
        .where(
            Attendance.lesson_id == lesson_id,
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False
        )
    )
    att_stats = session.exec(attendance_query).first()
    
    marked_count = int(att_stats[0] or 0)
    present_count = int(att_stats[1] or 0)
    absent_count = int(att_stats[2] or 0)
    
    return {
        "lesson_id": str(lesson_id),
        "lesson_name": lesson.name,
        "class_id": str(cls.id),
        "class_name": cls.name,
        "date": target_date.isoformat(),
        "attendance_exists": marked_count > 0,
        "total_students": total_students,
        "marked_count": marked_count,
        "present_count": present_count,
        "absent_count": absent_count,
        "not_marked_count": total_students - marked_count
    }
