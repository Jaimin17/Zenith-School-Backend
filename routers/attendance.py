import uuid
from datetime import date, timedelta, datetime, time
from typing import List, Optional

from fastapi import APIRouter, Query

from deps import AdminUser, StudentOrTeacherOrAdminUser, TeacherOrAdminUser
from core.database import SessionDep
from repository.attendance import attendanceOfWeek, attendanceOfStudentOfCurrentYear, attendanceBulkSave, \
    attendanceSave, attendanceUpdate, attendanceSoftDelete, getAttendanceByLesson
from schemas import AttendanceBase, AttendanceBulkSaveResponse, AttendanceBulkSave, AttendanceSaveResponse, \
    AttendanceSave, AttendanceUpdate, AttendanceListResponse

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


@router.post("/bulk-save", response_model=AttendanceBulkSaveResponse)
def bulkSaveAttendance(current_user: TeacherOrAdminUser, bulk_data: AttendanceBulkSave, session: SessionDep):
    user, role = current_user
    result = attendanceBulkSave(bulk_data, user.id, role, session)
    return result


@router.post("/save", response_model=AttendanceSaveResponse)
def saveAttendance(current_user: TeacherOrAdminUser, attendance_data: AttendanceSave, session: SessionDep):
    user, role = current_user
    result = attendanceSave(attendance_data, user.id, role, session)
    return result


@router.put("/update", response_model=AttendanceSaveResponse)
def updateAttendance(current_user: TeacherOrAdminUser, attendance_data: AttendanceUpdate, session: SessionDep):
    user, role = current_user
    result = attendanceUpdate(attendance_data, user.id, role, session)
    return result


@router.delete("/{id}", response_model=AttendanceSaveResponse)
def deleteAttendance(id: uuid.UUID, current_user: TeacherOrAdminUser, session: SessionDep):
    user, role = current_user
    result = attendanceSoftDelete(id, user.id, role, session)
    return result

@router.get("/lesson/{lesson_id}", response_model=AttendanceListResponse)
def getAttendanceForLesson(lesson_id: uuid.UUID, current_user: TeacherOrAdminUser, session: SessionDep, attendance_date: Optional[date] = Query(None, description="Filter by specific date")):
    user, role = current_user
    result = getAttendanceByLesson(lesson_id, attendance_date, user.id, role, session)
    return result