import uuid
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.database import SessionDep
from deps import (
    AdminUser,
    ParentUser,
    StudentOrParentOrAdminUser,
    StudentOrTeacherOrAdminUser,
    TeacherOrAdminUser,
)
from repository.attendance import (
    attendanceBulkSave,
    attendanceOfStudentOfCurrentYear,
    attendanceOfWeek,
    attendanceSave,
    attendanceSoftDelete,
    attendanceUpdate,
    checkAttendanceExists,
    getAttendanceByClass,
    getCalendarHeatmap,
    getClassAttendanceDetail,
    getClassesForDate,
    getClassRoster,
    getClasswiseSummary,
    getDashboardSummary,
    getParentChildrenAttendance,
    getStudentMonthlyAttendance,
    getTeacherClasses,
    takeAttendance,
)
from schemas import (
    AttendanceBase,
    AttendanceBulkSave,
    AttendanceBulkSaveResponse,
    AttendanceDashboardSummary,
    AttendanceListResponse,
    AttendanceSave,
    AttendanceSaveResponse,
    AttendanceTakeRequest,
    AttendanceTakeResponse,
    AttendanceUpdate,
    CalendarHeatmapResponse,
    ClassAttendanceDetailResponse,
    ClassesForDateResponse,
    ClassRosterResponse,
    ClasswiseAttendanceResponse,
    StudentMonthlyAttendance,
    TeacherClassSummary,
    TeacherClassesAttendanceResponse,
)

router = APIRouter(prefix="/attendance")


@router.get("/dashboard/summary", response_model=AttendanceDashboardSummary)
def getAttendanceDashboardSummary(
    current_user: AdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for summary (defaults to today)"),
):
    return getDashboardSummary(target_date or date.today(), session)


@router.get("/dashboard/classes", response_model=ClasswiseAttendanceResponse)
def getClasswiseAttendanceSummary(
    current_user: AdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for summary (defaults to today)"),
):
    return getClasswiseSummary(target_date or date.today(), session)


@router.get("/class/{class_id}", response_model=ClassAttendanceDetailResponse)
def getClassAttendance(
    class_id: uuid.UUID,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for attendance (defaults to today)"),
):
    return getClassAttendanceDetail(class_id, target_date or date.today(), session)


@router.get("/teacher/classes", response_model=TeacherClassesAttendanceResponse)
def getTeacherClassesSummary(
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for attendance status (defaults to today)"),
):
    user, role = current_user
    return getTeacherClasses(user.id, target_date or date.today(), session)


@router.get("/take/classes", response_model=ClassesForDateResponse)
def getClassesForTakingAttendance(
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date to get classes for (defaults to today)"),
    class_id: Optional[uuid.UUID] = Query(None, description="Filter by class ID"),
):
    user, role = current_user
    return getClassesForDate(target_date or date.today(), class_id, user.id, role, session)


@router.get("/take/roster/{class_id}", response_model=ClassRosterResponse)
def getClassRosterForAttendance(
    class_id: uuid.UUID,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for attendance (defaults to today)"),
):
    user, role = current_user
    return getClassRoster(class_id, target_date or date.today(), user.id, role, session)


@router.get("/take/check/{class_id}")
def checkClassAttendanceStatus(
    class_id: uuid.UUID,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date to check (defaults to today)"),
):
    return checkAttendanceExists(class_id, target_date or date.today(), session)


@router.post("/take", response_model=AttendanceTakeResponse)
def submitAttendance(
    request: AttendanceTakeRequest,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
):
    user, role = current_user
    return takeAttendance(request, user.id, role, session)


@router.get("/student/{student_id}/monthly", response_model=StudentMonthlyAttendance)
def getStudentMonthlyAttendanceRecords(
    student_id: uuid.UUID,
    current_user: StudentOrParentOrAdminUser,
    session: SessionDep,
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month 1-12 (defaults to current month)"),
):
    user, role = current_user
    if role == "student" and user.id != student_id:
        raise HTTPException(status_code=403, detail="You can only view your own attendance")
    if role == "parent":
        from models import Student
        from sqlmodel import select

        student = session.exec(select(Student).where(Student.id == student_id, Student.is_delete == False)).first()
        if not student or student.parent_id != user.id:
            raise HTTPException(status_code=403, detail="You can only view attendance of your children")

    today = date.today()
    return getStudentMonthlyAttendance(student_id, year or today.year, month or today.month, session)


@router.get("/student/{student_id}/calendar", response_model=CalendarHeatmapResponse)
def getStudentCalendarHeatmap(
    student_id: uuid.UUID,
    current_user: StudentOrParentOrAdminUser,
    session: SessionDep,
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month 1-12 (defaults to current month)"),
):
    user, role = current_user
    if role == "student" and user.id != student_id:
        raise HTTPException(status_code=403, detail="You can only view your own attendance")
    if role == "parent":
        from models import Student
        from sqlmodel import select

        student = session.exec(select(Student).where(Student.id == student_id, Student.is_delete == False)).first()
        if not student or student.parent_id != user.id:
            raise HTTPException(status_code=403, detail="You can only view attendance of your children")

    today = date.today()
    return getCalendarHeatmap(student_id, year or today.year, month or today.month, session)


@router.get("/parent/children", response_model=List[StudentMonthlyAttendance])
def getParentChildrenAttendanceSummary(
    current_user: ParentUser,
    session: SessionDep,
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month 1-12 (defaults to current month)"),
):
    user, _ = current_user
    today = date.today()
    return getParentChildrenAttendance(user.id, year or today.year, month or today.month, session)


@router.get("/getAttendanceOfCurrentWeek", response_model=List[AttendanceBase])
def getAttendanceOfCurrentWeek(current_user: AdminUser, session: SessionDep):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return attendanceOfWeek(session, datetime.combine(monday, time.min), datetime.combine(sunday, time.max))


@router.get("/getAttendanceOfStudent/{studentId}", response_model=List[AttendanceBase])
def getAttendanceOfStudent(current_user: StudentOrTeacherOrAdminUser, studentId: uuid.UUID, session: SessionDep):
    today = date.today()
    startDate = date(today.year, 6, 1) if today.month >= 6 else date(today.year - 1, 6, 1)
    return attendanceOfStudentOfCurrentYear(studentId, startDate, session)


@router.get("/class/{class_id}/records", response_model=AttendanceListResponse)
def getAttendanceForClass(
    class_id: uuid.UUID,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    attendance_date: Optional[date] = Query(None, description="Filter by specific date"),
):
    user, role = current_user
    return getAttendanceByClass(class_id, attendance_date, user.id, role, session)


@router.post("/bulk-save", response_model=AttendanceBulkSaveResponse)
def bulkSaveAttendance(current_user: TeacherOrAdminUser, bulk_data: AttendanceBulkSave, session: SessionDep):
    user, role = current_user
    return attendanceBulkSave(bulk_data, user.id, role, session)


@router.post("/save", response_model=AttendanceSaveResponse)
def saveAttendance(current_user: TeacherOrAdminUser, attendance_data: AttendanceSave, session: SessionDep):
    user, role = current_user
    return attendanceSave(attendance_data, user.id, role, session)


@router.put("/update", response_model=AttendanceSaveResponse)
def updateAttendance(current_user: TeacherOrAdminUser, attendance_data: AttendanceUpdate, session: SessionDep):
    user, role = current_user
    return attendanceUpdate(attendance_data, user.id, role, session)


@router.delete("/{id}", response_model=AttendanceSaveResponse)
def deleteAttendance(id: uuid.UUID, current_user: TeacherOrAdminUser, session: SessionDep):
    user, role = current_user
    return attendanceSoftDelete(id, user.id, role, session)
