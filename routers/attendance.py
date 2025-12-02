import uuid
from datetime import date, timedelta, datetime, time
from typing import List

from fastapi import APIRouter

from deps import AdminUser, StudentOrTeacherOrAdminUser
from core.database import SessionDep
from repository.attendance import attendanceOfWeek, attendanceOfStudentOfCurrentYear
from schemas import AttendanceBase

router = APIRouter(
    prefix="/attendance",
)

@router.get("/getAttendanceOfCurrentWeek", response_model=List[AttendanceBase])
def getAttendanceOfCurrentWeek(current_user: AdminUser, session: SessionDep):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    week_start_dt = datetime.combine(monday, time.min)
    week_end_dt = datetime.combine(sunday, time.max)

    result = attendanceOfWeek(session, week_start_dt, week_end_dt)
    return result

@router.get("/getAttendanceOfStudent/{studentId}", response_model=List[AttendanceBase])
def getAttendanceOfStudent(current_user: StudentOrTeacherOrAdminUser, studentId: uuid.UUID, session: SessionDep):
    today = date.today()
    if today.month >= 6:
        startDate = date(today.year, 6, 1)
    else:
        startDate = date(today.year - 1, 6, 1)

    result = attendanceOfStudentOfCurrentYear(studentId, startDate, session)
    return result