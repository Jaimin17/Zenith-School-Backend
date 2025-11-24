from datetime import datetime

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