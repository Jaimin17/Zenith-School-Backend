import uuid
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import case, distinct, func
from sqlmodel import Session, select

from models import Attendance, Class, Holiday, Student, Teacher
from schemas import (
    AttendanceBulkSave,
    AttendanceDashboardSummary,
    AttendanceDetail,
    AttendanceSave,
    AttendanceTakeRequest,
    AttendanceTakeResponse,
    AttendanceUpdate,
    CalendarDayData,
    CalendarHeatmapResponse,
    ClassAttendanceDetailResponse,
    ClassesForDateResponse,
    ClassForDateItem,
    ClassRosterResponse,
    ClassStudentAttendance,
    ClasswiseAttendanceResponse,
    ClassAttendanceSummary,
    StudentAttendanceRecord,
    StudentMonthlyAttendance,
    StudentRosterItem,
    TeacherClassSummary,
)


def _holiday_reason(target_date: date, session: Session) -> Optional[str]:
    if target_date.weekday() == 6:
        return "Sunday"
    holiday = session.exec(select(Holiday).where(func.date(Holiday.date) == target_date)).first()
    return holiday.name if holiday else None


def _active_students_for_class(class_id: uuid.UUID, session: Session):
    return session.exec(
        select(Student)
        .where(Student.class_id == class_id, Student.is_delete == False)
        .order_by(Student.first_name, Student.last_name)
    ).all()


def _ensure_daily_attendance(class_id: uuid.UUID, target_date: date, session: Session):
    students = _active_students_for_class(class_id, session)
    existing = session.exec(
        select(Attendance).where(
            Attendance.class_id == class_id,
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False,
        )
    ).all()

    existing_map = {row.student_id: row for row in existing}
    missing = [s for s in students if s.id not in existing_map]

    if missing:
        attendance_dt = datetime.combine(target_date, time(9, 0))
        for student in missing:
            session.add(
                Attendance(
                    student_id=student.id,
                    class_id=class_id,
                    attendance_date=attendance_dt,
                    present=True,
                    is_delete=False,
                )
            )
        session.commit()
        existing = session.exec(
            select(Attendance).where(
                Attendance.class_id == class_id,
                func.date(Attendance.attendance_date) == target_date,
                Attendance.is_delete == False,
            )
        ).all()

    return students, existing


def attendanceOfWeek(session: Session, monday: datetime, sunday: datetime):
    return session.exec(
        select(Attendance)
        .where(
            Attendance.attendance_date >= monday,
            Attendance.attendance_date <= sunday,
            Attendance.is_delete == False,
        )
        .order_by(Attendance.attendance_date.desc())
    ).all()


def attendanceOfStudentOfCurrentYear(studentId: uuid.UUID, startDate: date, session: Session):
    return session.exec(
        select(Attendance)
        .where(
            Attendance.attendance_date >= startDate,
            Attendance.student_id == studentId,
            Attendance.is_delete == False,
        )
        .order_by(Attendance.attendance_date.desc())
    ).all()


def getAttendanceByClass(class_id: uuid.UUID, attendance_date: Optional[date], userId: uuid.UUID, role: str, session: Session):
    class_obj = session.exec(select(Class).where(Class.id == class_id, Class.is_delete == False)).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    query = (
        select(Attendance, Student)
        .join(Student, Attendance.student_id == Student.id)
        .where(Attendance.class_id == class_id, Attendance.is_delete == False)
    )
    if attendance_date:
        query = query.where(func.date(Attendance.attendance_date) == attendance_date)

    rows = session.exec(query.order_by(Attendance.attendance_date.desc())).all()
    details = [
        AttendanceDetail(
            id=att.id,
            student_id=student.id,
            student_name=f"{student.first_name} {student.last_name}",
            class_id=class_id,
            class_name=class_obj.name,
            attendance_date=att.attendance_date.date(),
            present=att.present,
            is_delete=att.is_delete,
        )
        for att, student in rows
    ]
    return {"attendances": details, "total": len(details)}


def attendanceBulkSave(bulk_data: AttendanceBulkSave, userId: uuid.UUID, role: str, session: Session):
    request = AttendanceTakeRequest(
        class_id=bulk_data.class_id,
        attendance_date=bulk_data.attendance_date,
        records=bulk_data.attendances,
        overwrite_existing=False,
    )
    result = takeAttendance(request, userId, role, session)
    return {"message": result.message, "total_saved": result.created_count + result.updated_count, "failed": []}


def attendanceSave(attendance_data: AttendanceSave, userId: uuid.UUID, role: str, session: Session):
    request = AttendanceTakeRequest(
        class_id=attendance_data.class_id,
        attendance_date=attendance_data.attendance_date,
        records=[{"student_id": attendance_data.student_id, "present": attendance_data.present}],
        overwrite_existing=True,
    )
    result = takeAttendance(request, userId, role, session)
    return {"id": str(attendance_data.student_id), "message": result.message}


def attendanceUpdate(attendance_data: AttendanceUpdate, userId: uuid.UUID, role: str, session: Session):
    attendance = session.exec(select(Attendance).where(Attendance.id == attendance_data.id, Attendance.is_delete == False)).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    if role == "teacher":
        class_obj = session.exec(select(Class).where(Class.id == attendance.class_id, Class.is_delete == False)).first()
        if not class_obj or class_obj.supervisor_id != userId:
            raise HTTPException(status_code=403, detail="You are not authorized to update this attendance record.")

    attendance.present = attendance_data.present
    session.add(attendance)
    session.commit()
    return {"id": str(attendance.id), "message": "Attendance updated successfully"}


def attendanceSoftDelete(id: uuid.UUID, userId: uuid.UUID, role: str, session: Session):
    attendance = session.exec(select(Attendance).where(Attendance.id == id, Attendance.is_delete == False)).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    if role == "teacher":
        class_obj = session.exec(select(Class).where(Class.id == attendance.class_id, Class.is_delete == False)).first()
        if not class_obj or class_obj.supervisor_id != userId:
            raise HTTPException(status_code=403, detail="You are not authorized to delete this attendance record.")

    attendance.is_delete = True
    session.add(attendance)
    session.commit()
    return {"id": str(id), "message": "Attendance deleted successfully"}


def getDashboardSummary(target_date: date, session: Session) -> AttendanceDashboardSummary:
    total_classes = session.exec(select(func.count(Class.id)).where(Class.is_delete == False)).first() or 0
    total_students = session.exec(select(func.count(Student.id)).where(Student.is_delete == False)).first() or 0

    reason = _holiday_reason(target_date, session)
    if reason:
        return AttendanceDashboardSummary(
            date=target_date,
            total_classes=int(total_classes),
            classes_with_attendance=0,
            pending_classes=0,
            total_students=int(total_students),
            present_count=0,
            absent_count=0,
            attendance_rate=0.0,
        )

    class_ids = session.exec(select(Class.id).where(Class.is_delete == False)).all()
    for class_id in class_ids:
        _ensure_daily_attendance(class_id, target_date, session)

    attendance_stats = session.exec(
        select(
            func.count(Attendance.id).label("total"),
            func.sum(case((Attendance.present == True, 1), else_=0)).label("present"),
            func.sum(case((Attendance.present == False, 1), else_=0)).label("absent"),
        ).where(func.date(Attendance.attendance_date) == target_date, Attendance.is_delete == False)
    ).first()

    present_count = int(attendance_stats[1] or 0)
    absent_count = int(attendance_stats[2] or 0)
    total_attendance = int(attendance_stats[0] or 0)

    classes_with_attendance = session.exec(
        select(func.count(distinct(Attendance.class_id))).where(
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False,
        )
    ).first() or 0

    pending_classes = max(0, int(total_classes) - int(classes_with_attendance))
    attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0.0

    return AttendanceDashboardSummary(
        date=target_date,
        total_classes=int(total_classes),
        classes_with_attendance=int(classes_with_attendance),
        pending_classes=int(pending_classes),
        total_students=int(total_students),
        present_count=present_count,
        absent_count=absent_count,
        attendance_rate=round(attendance_rate, 2),
    )


def getClasswiseSummary(target_date: date, session: Session) -> ClasswiseAttendanceResponse:
    classes = session.exec(select(Class).where(Class.is_delete == False).order_by(Class.name)).all()
    reason = _holiday_reason(target_date, session)
    summaries = []

    for cls in classes:
        total_students = session.exec(
            select(func.count(Student.id)).where(Student.class_id == cls.id, Student.is_delete == False)
        ).first() or 0

        if reason:
            summaries.append(
                ClassAttendanceSummary(
                    class_id=cls.id,
                    class_name=cls.name,
                    grade_level=cls.grade.level if cls.grade else None,
                    total_students=int(total_students),
                    present_count=0,
                    absent_count=0,
                    not_marked_count=0,
                    attendance_rate=0.0,
                    has_attendance=False,
                )
            )
            continue

        _, attendance_rows = _ensure_daily_attendance(cls.id, target_date, session)
        present_count = sum(1 for row in attendance_rows if row.present)
        absent_count = sum(1 for row in attendance_rows if not row.present)
        marked_count = len(attendance_rows)
        not_marked_count = max(0, int(total_students) - marked_count)
        attendance_rate = (present_count / marked_count * 100) if marked_count > 0 else 0.0

        summaries.append(
            ClassAttendanceSummary(
                class_id=cls.id,
                class_name=cls.name,
                grade_level=cls.grade.level if cls.grade else None,
                total_students=int(total_students),
                present_count=int(present_count),
                absent_count=int(absent_count),
                not_marked_count=int(not_marked_count),
                attendance_rate=round(attendance_rate, 2),
                has_attendance=marked_count > 0,
            )
        )

    return ClasswiseAttendanceResponse(date=target_date, classes=summaries, total_classes=len(summaries))


def getClassAttendanceDetail(class_id: uuid.UUID, target_date: date, session: Session) -> ClassAttendanceDetailResponse:
    cls = session.exec(select(Class).where(Class.id == class_id, Class.is_delete == False)).first()
    if not cls:
        raise HTTPException(status_code=404, detail=f"Class not found with ID: {class_id}")

    reason = _holiday_reason(target_date, session)
    if reason:
        raise HTTPException(status_code=400, detail=f"Attendance is not available on {reason}.")

    students, attendance_rows = _ensure_daily_attendance(class_id, target_date, session)
    attendance_map = {row.student_id: row for row in attendance_rows}

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
            student_attendances.append(
                ClassStudentAttendance(
                    student_id=student.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    username=student.username,
                    attendance_id=attendance.id,
                    present=attendance.present,
                    marked_at=attendance.attendance_date,
                )
            )
        else:
            not_marked_count += 1
            student_attendances.append(
                ClassStudentAttendance(
                    student_id=student.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    username=student.username,
                    attendance_id=None,
                    present=None,
                    marked_at=None,
                )
            )

    return ClassAttendanceDetailResponse(
        class_id=cls.id,
        class_name=cls.name,
        date=target_date,
        lesson_id=None,
        lesson_name=None,
        total_students=len(students),
        present_count=present_count,
        absent_count=absent_count,
        not_marked_count=not_marked_count,
        students=student_attendances,
    )


def getStudentMonthlyAttendance(student_id: uuid.UUID, year: int, month: int, session: Session) -> StudentMonthlyAttendance:
    student = session.exec(select(Student).where(Student.id == student_id, Student.is_delete == False)).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found with ID: {student_id}")

    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    results = session.exec(
        select(Attendance, Class)
        .join(Class, Attendance.class_id == Class.id)
        .where(
            Attendance.student_id == student_id,
            func.date(Attendance.attendance_date) >= start_date,
            func.date(Attendance.attendance_date) <= end_date,
            Attendance.is_delete == False,
            Class.is_delete == False,
        )
        .order_by(Attendance.attendance_date.desc())
    ).all()

    records = []
    present_days = 0
    absent_days = 0
    for attendance, cls in results:
        if attendance.present:
            present_days += 1
        else:
            absent_days += 1
        records.append(
            StudentAttendanceRecord(
                id=attendance.id,
                date=attendance.attendance_date.date(),
                present=attendance.present,
                class_id=cls.id,
                class_name=cls.name,
                subject_name=None,
            )
        )

    total_days = present_days + absent_days
    rate = (present_days / total_days * 100) if total_days > 0 else 0.0

    return StudentMonthlyAttendance(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        month=month,
        year=year,
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        attendance_rate=round(rate, 2),
        records=records,
    )


def getCalendarHeatmap(student_id: uuid.UUID, year: int, month: int, session: Session) -> CalendarHeatmapResponse:
    student = session.exec(select(Student).where(Student.id == student_id, Student.is_delete == False)).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found with ID: {student_id}")

    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    results = session.exec(
        select(
            func.date(Attendance.attendance_date).label("att_date"),
            func.count(Attendance.id).label("total"),
            func.sum(case((Attendance.present == True, 1), else_=0)).label("present"),
            func.sum(case((Attendance.present == False, 1), else_=0)).label("absent"),
        )
        .where(
            Attendance.student_id == student_id,
            func.date(Attendance.attendance_date) >= start_date,
            func.date(Attendance.attendance_date) <= end_date,
            Attendance.is_delete == False,
        )
        .group_by(func.date(Attendance.attendance_date))
        .order_by(func.date(Attendance.attendance_date))
    ).all()

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
        days_data.append(
            CalendarDayData(
                date=att_date,
                present_count=present,
                absent_count=absent,
                total_records=total,
                attendance_rate=round(rate, 2),
            )
        )

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
            "attendance_rate": round(monthly_rate, 2),
        },
    )


def getTeacherClasses(teacher_id: uuid.UUID, target_date: date, session: Session) -> list[TeacherClassSummary]:
    classes = session.exec(
        select(Class).where(Class.supervisor_id == teacher_id, Class.is_delete == False).order_by(Class.name)
    ).all()

    reason = _holiday_reason(target_date, session)
    summaries = []
    for cls in classes:
        total_students = session.exec(
            select(func.count(Student.id)).where(Student.class_id == cls.id, Student.is_delete == False)
        ).first() or 0

        present_count = 0
        absent_count = 0
        attendance_marked = False

        if not reason:
            _, rows = _ensure_daily_attendance(cls.id, target_date, session)
            present_count = sum(1 for row in rows if row.present)
            absent_count = sum(1 for row in rows if not row.present)
            attendance_marked = len(rows) > 0

        summaries.append(
            TeacherClassSummary(
                class_id=cls.id,
                class_name=cls.name,
                lesson_id=None,
                lesson_name=cls.name,
                subject_name=None,
                day=target_date.strftime("%A").upper(),
                total_students=int(total_students),
                attendance_marked=attendance_marked,
                present_count=int(present_count),
                absent_count=int(absent_count),
            )
        )

    return summaries


def getParentChildrenAttendance(parent_id: uuid.UUID, year: int, month: int, session: Session) -> list[StudentMonthlyAttendance]:
    children = session.exec(select(Student).where(Student.parent_id == parent_id, Student.is_delete == False)).all()
    if not children:
        raise HTTPException(status_code=404, detail="No children found for this parent")
    return [getStudentMonthlyAttendance(child.id, year, month, session) for child in children]


def getClassRoster(class_id: uuid.UUID, target_date: date, user_id: uuid.UUID, role: str, session: Session) -> ClassRosterResponse:
    reason = _holiday_reason(target_date, session)
    if reason:
        raise HTTPException(status_code=400, detail={"status": "holiday", "reason": reason})

    cls = session.exec(select(Class).where(Class.id == class_id, Class.is_delete == False)).first()
    if not cls:
        raise HTTPException(status_code=404, detail=f"Class not found with ID: {class_id}")

    if role == "teacher" and cls.supervisor_id != user_id:
        raise HTTPException(status_code=403, detail="You are not authorized to take attendance for this class.")

    students, attendance_rows = _ensure_daily_attendance(class_id, target_date, session)
    attendance_map = {att.student_id: att for att in attendance_rows}

    roster_items = []
    for student in students:
        att = attendance_map.get(student.id)
        roster_items.append(
            StudentRosterItem(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                username=student.username,
                img=student.img,
                attendance_id=att.id if att else None,
                present=att.present if att else None,
            )
        )

    return ClassRosterResponse(
        class_id=cls.id,
        class_name=cls.name,
        target_date=target_date,
        total_students=len(students),
        attendance_exists=len(attendance_rows) > 0,
        marked_count=len(attendance_rows),
        students=roster_items,
    )


def getClassesForDate(target_date: date, class_id: Optional[uuid.UUID], user_id: uuid.UUID, role: str, session: Session) -> ClassesForDateResponse:
    day_of_week = target_date.strftime("%A")
    reason = _holiday_reason(target_date, session)
    if reason:
        return ClassesForDateResponse(date=target_date, day_of_week=day_of_week, total_classes=0, classes=[])

    query = select(Class, Teacher).outerjoin(Teacher, Class.supervisor_id == Teacher.id).where(Class.is_delete == False)
    if class_id:
        query = query.where(Class.id == class_id)
    if role == "teacher":
        query = query.where(Class.supervisor_id == user_id)

    results = session.exec(query.order_by(Class.name)).all()
    class_items = []

    for cls, teacher in results:
        students, attendance_rows = _ensure_daily_attendance(cls.id, target_date, session)
        present_count = sum(1 for row in attendance_rows if row.present)
        absent_count = sum(1 for row in attendance_rows if not row.present)
        marked_count = len(attendance_rows)

        if marked_count == 0:
            status = "not_taken"
        elif marked_count < len(students):
            status = "partial"
        else:
            status = "complete"

        class_items.append(
            ClassForDateItem(
                class_id=cls.id,
                class_name=cls.name,
                teacher_id=teacher.id if teacher else None,
                teacher_name=f"{teacher.first_name} {teacher.last_name}" if teacher else None,
                attendance_status=status,
                students_count=len(students),
                present_count=present_count,
                absent_count=absent_count,
            )
        )

    return ClassesForDateResponse(
        date=target_date,
        day_of_week=day_of_week,
        total_classes=len(class_items),
        classes=class_items,
    )


def takeAttendance(request: AttendanceTakeRequest, user_id: uuid.UUID, role: str, session: Session) -> AttendanceTakeResponse:
    reason = _holiday_reason(request.attendance_date, session)
    if reason:
        raise HTTPException(status_code=400, detail=f"Attendance cannot be taken on {reason}.")

    cls = session.exec(select(Class).where(Class.id == request.class_id, Class.is_delete == False)).first()
    if not cls:
        raise HTTPException(status_code=404, detail=f"Class not found with ID: {request.class_id}")

    if role == "teacher" and cls.supervisor_id != user_id:
        raise HTTPException(status_code=403, detail="You are not authorized to take attendance for this class.")

    valid_students = _active_students_for_class(request.class_id, session)
    valid_student_ids = {student.id for student in valid_students}
    provided_student_ids = {record.student_id for record in request.records}

    invalid_students = provided_student_ids - valid_student_ids
    if invalid_students:
        raise HTTPException(status_code=400, detail=f"Invalid student IDs for this class: {', '.join(str(sid) for sid in invalid_students)}")

    if len(provided_student_ids) != len(request.records):
        raise HTTPException(status_code=400, detail="Duplicate student IDs found in attendance records.")

    existing_attendance = session.exec(
        select(Attendance).where(
            Attendance.class_id == request.class_id,
            func.date(Attendance.attendance_date) == request.attendance_date,
            Attendance.student_id.in_(provided_student_ids),
            Attendance.is_delete == False,
        )
    ).all()

    if existing_attendance and not request.overwrite_existing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Attendance already exists for {len(existing_attendance)} students on {request.attendance_date}",
                "hint": "Set 'overwrite_existing: true' to update existing records",
            },
        )

    existing_map = {att.student_id: att for att in existing_attendance}
    created_count = 0
    updated_count = 0
    present_count = 0
    absent_count = 0
    attendance_dt = datetime.combine(request.attendance_date, time(9, 0))

    for record in request.records:
        if record.present:
            present_count += 1
        else:
            absent_count += 1

        existing = existing_map.get(record.student_id)
        if existing:
            existing.present = record.present
            existing.attendance_date = attendance_dt
            session.add(existing)
            updated_count += 1
        else:
            session.add(
                Attendance(
                    student_id=record.student_id,
                    class_id=request.class_id,
                    attendance_date=attendance_dt,
                    present=record.present,
                    is_delete=False,
                )
            )
            created_count += 1

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Database error while saving attendance records.")

    return AttendanceTakeResponse(
        message="Attendance saved successfully",
        class_id=request.class_id,
        attendance_date=request.attendance_date,
        total_students=len(request.records),
        created_count=created_count,
        updated_count=updated_count,
        present_count=present_count,
        absent_count=absent_count,
    )


def checkAttendanceExists(class_id: uuid.UUID, target_date: date, session: Session) -> dict:
    cls = session.exec(select(Class).where(Class.id == class_id, Class.is_delete == False)).first()
    if not cls:
        raise HTTPException(status_code=404, detail=f"Class not found with ID: {class_id}")

    reason = _holiday_reason(target_date, session)
    if reason:
        return {
            "class_id": str(class_id),
            "class_name": cls.name,
            "date": target_date.isoformat(),
            "attendance_exists": False,
            "total_students": 0,
            "marked_count": 0,
            "present_count": 0,
            "absent_count": 0,
            "not_marked_count": 0,
            "is_holiday": True,
            "holiday_reason": reason,
        }

    total_students = session.exec(
        select(func.count(Student.id)).where(Student.class_id == class_id, Student.is_delete == False)
    ).first() or 0

    stats = session.exec(
        select(
            func.count(Attendance.id).label("total"),
            func.sum(case((Attendance.present == True, 1), else_=0)).label("present"),
            func.sum(case((Attendance.present == False, 1), else_=0)).label("absent"),
        ).where(
            Attendance.class_id == class_id,
            func.date(Attendance.attendance_date) == target_date,
            Attendance.is_delete == False,
        )
    ).first()

    marked_count = int(stats[0] or 0)
    present_count = int(stats[1] or 0)
    absent_count = int(stats[2] or 0)

    return {
        "class_id": str(class_id),
        "class_name": cls.name,
        "date": target_date.isoformat(),
        "attendance_exists": marked_count > 0,
        "total_students": int(total_students),
        "marked_count": marked_count,
        "present_count": present_count,
        "absent_count": absent_count,
        "not_marked_count": int(total_students) - marked_count,
        "is_holiday": False,
        "holiday_reason": None,
    }


def getStudentAttendanceByDateRange(student_id: uuid.UUID, start_date: date, end_date: date, session: Session):
    rows = session.exec(
        select(Attendance, Class)
        .join(Class, Attendance.class_id == Class.id)
        .where(
            Attendance.student_id == student_id,
            func.date(Attendance.attendance_date) >= start_date,
            func.date(Attendance.attendance_date) <= end_date,
            Attendance.is_delete == False,
            Class.is_delete == False,
        )
        .order_by(Attendance.attendance_date.desc())
    ).all()

    return [
        StudentAttendanceRecord(
            id=att.id,
            date=att.attendance_date.date(),
            present=att.present,
            class_id=cls.id,
            class_name=cls.name,
            subject_name=None,
        )
        for att, cls in rows
    ]


def getStudentYearAttendanceSummary(student_id: uuid.UUID, start_date: date, end_date: date, session: Session):
    today = date.today()

    # Collect all holiday dates in full year range (date-only)
    holiday_dates = {
        h.date.date()
        for h in session.exec(
            select(Holiday).where(
                func.date(Holiday.date) >= start_date,
                func.date(Holiday.date) <= end_date,
            )
        ).all()
    }
    public_holiday_count = sum(1 for day in holiday_dates if day.weekday() != 6)

    passed_end = min(today, end_date)
    passed_working_days = 0
    if start_date <= passed_end:
        cursor = start_date
        while cursor <= passed_end:
            if cursor.weekday() != 6 and cursor not in holiday_dates:
                passed_working_days += 1
            cursor += timedelta(days=1)

    left_start = max(start_date, today + timedelta(days=1))
    working_days_left = 0
    if left_start <= end_date:
        cursor = left_start
        while cursor <= end_date:
            if cursor.weekday() != 6 and cursor not in holiday_dates:
                working_days_left += 1
            cursor += timedelta(days=1)

    rows = session.exec(
        select(Attendance).where(
            Attendance.student_id == student_id,
            func.date(Attendance.attendance_date) >= start_date,
            func.date(Attendance.attendance_date) <= passed_end,
            Attendance.is_delete == False,
        )
    ).all()

    # One attendance should exist per day, but in case of duplicate records we
    # mark a day absent if any record for that day is absent.
    daily_status: dict[date, bool] = {}
    for row in rows:
        day = row.attendance_date.date()
        if day.weekday() == 6 or day in holiday_dates:
            continue
        if day not in daily_status:
            daily_status[day] = row.present
        else:
            daily_status[day] = daily_status[day] and row.present

    absent_days = sum(1 for present in daily_status.values() if not present)
    present_days = max(0, passed_working_days - absent_days)
    attendance_percentage = (present_days / passed_working_days * 100) if passed_working_days > 0 else 0.0

    return {
        "total_working_days": int(passed_working_days),
        "working_days_left": int(working_days_left),
        "public_holiday_count": int(public_holiday_count),
        "present_days": int(present_days),
        "absent_days": int(absent_days),
        "attendance_percentage": round(attendance_percentage, 2),
    }
