import uuid
from datetime import datetime, date

from sqlmodel import Session, select

from models import Attendance


def attendanceOfWeek(session: Session, monday: datetime, sunday: datetime):
    query = (
        select(Attendance)
        .where(
            Attendance.attendance_date >= monday,
            Attendance.attendance_date <= sunday,
        )
    )

    attendance = session.exec(query).all()
    return attendance

def attendanceOfStudentOfCurrentYear(studentId: uuid.UUID, startDate: date, session: Session):
    query = (
        select(Attendance)
        .where(Attendance.attendance_date >= startDate, Attendance.student_id == studentId)
    )

    attendance = session.exec(query).all()
    return attendance