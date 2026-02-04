import uuid
from datetime import date, timedelta, datetime, time
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi import HTTPException
from deps import AdminUser, StudentOrTeacherOrAdminUser, TeacherOrAdminUser, StudentOrParentUser, StudentOrParentOrAdminUser, ParentUser
from core.database import SessionDep
from repository.attendance import (
    attendanceOfWeek, attendanceOfStudentOfCurrentYear, attendanceBulkSave,
    attendanceSave, attendanceUpdate, attendanceSoftDelete, getAttendanceByLesson,
    getDashboardSummary, getClasswiseSummary, getClassAttendanceDetail,
    getStudentMonthlyAttendance, getCalendarHeatmap, getTeacherClasses,
    getParentChildrenAttendance, getLessonRoster, getLessonsForDate,
    takeAttendance, checkAttendanceExists
)
from schemas import (
    AttendanceBase, AttendanceBulkSaveResponse, AttendanceBulkSave, AttendanceSaveResponse,
    AttendanceSave, AttendanceUpdate, AttendanceListResponse, AttendanceDashboardSummary,
    ClasswiseAttendanceResponse, ClassAttendanceDetailResponse, StudentMonthlyAttendance,
    CalendarHeatmapResponse, TeacherClassSummary, LessonRosterResponse, LessonsForDateResponse,
    AttendanceTakeRequest, AttendanceTakeResponse
)

router = APIRouter(
    prefix="/attendance",
)


# ===================== Admin Dashboard Endpoints =====================

@router.get("/dashboard/summary", response_model=AttendanceDashboardSummary)
def getAttendanceDashboardSummary(
    current_user: AdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for summary (defaults to today)")
):
    """
    Admin Dashboard: Get attendance summary for a specific date.
    Returns total classes, classes with attendance, pending, present/absent counts, attendance rate.
    """
    if target_date is None:
        target_date = date.today()
    return getDashboardSummary(target_date, session)


@router.get("/dashboard/classes", response_model=ClasswiseAttendanceResponse)
def getClasswiseAttendanceSummary(
    current_user: AdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for summary (defaults to today)")
):
    """
    Admin Dashboard: Get class-wise attendance summary for a specific date.
    Click on a date in dashboard -> shows all classes with their attendance stats.
    """
    if target_date is None:
        target_date = date.today()
    return getClasswiseSummary(target_date, session)


@router.get("/class/{class_id}", response_model=ClassAttendanceDetailResponse)
def getClassAttendance(
    class_id: uuid.UUID,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for attendance (defaults to today)")
):
    """
    Get detailed attendance for a specific class on a specific date.
    Admin: Can view any class.
    Teacher: Can only view classes they teach (verified in repository).
    Returns all students with their attendance status (present/absent/not marked).
    """
    if target_date is None:
        target_date = date.today()
    return getClassAttendanceDetail(class_id, target_date, session)


# ===================== Teacher View Endpoints =====================

@router.get("/teacher/classes", response_model=List[TeacherClassSummary])
def getTeacherClassesSummary(
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for attendance status (defaults to today)")
):
    """
    Teacher View: Get list of classes assigned to the teacher with attendance status.
    Shows which classes have attendance marked for the specified date.
    """
    user, role = current_user
    if target_date is None:
        target_date = date.today()
    
    # For admin, this would need a teacher_id parameter
    # For teacher, use their own ID
    if role == "teacher":
        return getTeacherClasses(user.id, target_date, session)
    else:
        # Admin can optionally pass a teacher_id as query param in future
        # For now, return empty list for admin (they use dashboard instead)
        return []


# ===================== Take Attendance Workflow Endpoints =====================

@router.get("/take/lessons", response_model=LessonsForDateResponse)
def getLessonsForTakingAttendance(
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date to get lessons for (defaults to today)"),
    class_id: Optional[uuid.UUID] = Query(None, description="Filter by class ID")
):
    """
    Step 1-2 of Take Attendance: Get lessons for a specific date.
    - Teachers see only their assigned lessons
    - Admins see all lessons (can filter by class)
    - Returns attendance status for each lesson (not_taken, partial, complete)
    """
    user, role = current_user
    if target_date is None:
        target_date = date.today()
    
    return getLessonsForDate(target_date, class_id, user.id, role, session)


@router.get("/take/roster/{lesson_id}", response_model=LessonRosterResponse)
def getLessonRosterForAttendance(
    lesson_id: uuid.UUID,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date for attendance (defaults to today)")
):
    """
    Step 3 of Take Attendance: Get student roster for a lesson.
    - Returns all students in the class with their current attendance status
    - If attendance_exists is True, this is "Edit" mode
    - Shows which students are already marked present/absent
    """
    user, role = current_user
    if target_date is None:
        target_date = date.today()
    
    return getLessonRoster(lesson_id, target_date, user.id, role, session)


@router.get("/take/check/{lesson_id}")
def checkLessonAttendanceStatus(
    lesson_id: uuid.UUID,
    current_user: TeacherOrAdminUser,
    session: SessionDep,
    target_date: Optional[date] = Query(None, description="Date to check (defaults to today)")
):
    """
    Check if attendance exists for a lesson on a specific date.
    Use this before showing the "Take Attendance" form to determine if it's
    create mode or edit mode.
    """
    if target_date is None:
        target_date = date.today()
    
    return checkAttendanceExists(lesson_id, target_date, session)


@router.post("/take", response_model=AttendanceTakeResponse)
def submitAttendance(
    request: AttendanceTakeRequest,
    current_user: TeacherOrAdminUser,
    session: SessionDep
):
    """
    Submit attendance for a lesson (create or update).
    
    Request body:
    - lesson_id: UUID of the lesson
    - attendance_date: Date for the attendance
    - records: List of {student_id, present} objects
    - overwrite_existing: Set to true to update existing records (edit mode)
    
    Validation:
    - All students must belong to the lesson's class
    - No duplicate student IDs allowed
    - If overwrite_existing is false and records exist, returns 409 error
    """
    user, role = current_user
    return takeAttendance(request, user.id, role, session)


# ===================== Student/Parent View Endpoints =====================

@router.get("/student/{student_id}/monthly", response_model=StudentMonthlyAttendance)
def getStudentMonthlyAttendanceRecords(
    student_id: uuid.UUID,
    current_user: StudentOrParentOrAdminUser,
    session: SessionDep,
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month 1-12 (defaults to current month)")
):
    """
    Get monthly attendance records for a specific student.
    Student: Can only view their own attendance.
    Parent: Can view attendance of their children.
    Admin: Can view any student's attendance.
    """
    user, role = current_user
    
    # Validate access
    if role == "student" and user.id != student_id:
        raise HTTPException(status_code=403, detail="You can only view your own attendance")
    elif role == "parent":
        from sqlmodel import select
        from models import Student
        # Verify this student belongs to the parent
        student = session.exec(select(Student).where(Student.id == student_id, Student.is_delete == False)).first()
        if not student or student.parent_id != user.id:
            raise HTTPException(status_code=403, detail="You can only view attendance of your children")
    
    if year is None:
        year = date.today().year
    if month is None:
        month = date.today().month
    
    return getStudentMonthlyAttendance(student_id, year, month, session)


@router.get("/student/{student_id}/calendar", response_model=CalendarHeatmapResponse)
def getStudentCalendarHeatmap(
    student_id: uuid.UUID,
    current_user: StudentOrParentOrAdminUser,
    session: SessionDep,
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month 1-12 (defaults to current month)")
):
    """
    Get calendar heatmap data for a student's attendance.
    Returns daily attendance rates for color-coded calendar visualization.
    Green = present, Red = absent, Gray = no records.
    """
    user, role = current_user
    
    # Validate access
    if role == "student" and user.id != student_id:
        raise HTTPException(status_code=403, detail="You can only view your own attendance")
    elif role == "parent":
        from sqlmodel import select
        from models import Student
        # Verify this student belongs to the parent
        student = session.exec(select(Student).where(Student.id == student_id, Student.is_delete == False)).first()
        if not student or student.parent_id != user.id:
            raise HTTPException(status_code=403, detail="You can only view attendance of your children")
    
    if year is None:
        year = date.today().year
    if month is None:
        month = date.today().month
    
    return getCalendarHeatmap(student_id, year, month, session)


@router.get("/parent/children", response_model=List[StudentMonthlyAttendance])
def getParentChildrenAttendanceSummary(
    current_user: ParentUser,
    session: SessionDep,
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month 1-12 (defaults to current month)")
):
    """
    Parent View: Get monthly attendance for all children.
    Returns attendance summary for each child in one call.
    """
    user, role = current_user
    
    if year is None:
        year = date.today().year
    if month is None:
        month = date.today().month
    
    return getParentChildrenAttendance(user.id, year, month, session)


# ===================== Existing Endpoints (kept for backward compatibility) =====================


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


@router.get("/lesson/{lesson_id}", response_model=AttendanceListResponse)
def getAttendanceForLesson(lesson_id: uuid.UUID, current_user: TeacherOrAdminUser, session: SessionDep,
                           attendance_date: Optional[date] = Query(None, description="Filter by specific date")):
    user, role = current_user
    result = getAttendanceByLesson(lesson_id, attendance_date, user.id, role, session)
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
