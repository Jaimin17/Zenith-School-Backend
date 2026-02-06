import uuid
from datetime import datetime, date
from typing import List, Optional

from fastapi import Form
from pydantic import EmailStr, BaseModel, field_validator, ConfigDict
from sqlmodel import SQLModel, Field

from models import UserSex, Day


class PaginatedBaseResponse(BaseModel):
    total_count: int
    page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class UserBase(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    is_active: bool
    is_superuser: bool


class userDetailBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    address: str
    created_at: datetime


class RegisterUser(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    firstName: str
    lastName: str
    email: EmailStr
    password: str


class AdminResponse(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str


class ParentResponse(userDetailBase):
    model_config = ConfigDict(from_attributes=True)


class TeacherResponse(userDetailBase):
    model_config = ConfigDict(from_attributes=True)

    img: Optional[str] = None
    blood_type: str
    sex: str
    dob: date


class StudentResponse(userDetailBase):
    model_config = ConfigDict(from_attributes=True)

    img: Optional[str] = None
    blood_type: str
    sex: str
    dob: date
    parent_id: Optional[uuid.UUID] = None
    class_id: Optional[uuid.UUID] = None
    grade_id: Optional[uuid.UUID] = None


class UserPublic(SQLModel):
    id: uuid.UUID


class Token(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenWithUser(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: dict  # Will contain the appropriate user response based on role
    role: str


class RefreshTokenRequest(SQLModel):
    refresh_token: str


class TokenPayload(SQLModel):
    sub: str  # username
    role: str  # role
    user_id: str  # id
    exp: int | None = None


# ===================== Base Schemas =====================

class SubjectBase(SQLModel):
    id: uuid.UUID
    name: str


class GradeBase(SQLModel):
    id: uuid.UUID
    level: int


class ClassBase(SQLModel):
    id: uuid.UUID
    name: str
    capacity: int


class LessonBase(SQLModel):
    id: uuid.UUID
    name: str
    day: Day
    start_time: datetime
    end_time: datetime
    subject: Optional[SubjectBase] = None
    related_class: Optional[ClassBase] = None


class ParentBase(SQLModel):
    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    address: str


class StudentBase(SQLModel):
    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    address: str
    img: Optional[str] = None
    blood_type: str
    sex: UserSex
    dob: date


class TeacherBase(SQLModel):
    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    address: str
    img: Optional[str] = None
    blood_type: str
    sex: UserSex
    dob: date


class EventBase(SQLModel):
    id: uuid.UUID
    title: str
    description: str
    start_time: datetime
    end_time: datetime


class AnnouncementBase(SQLModel):
    id: uuid.UUID
    title: str
    description: str
    announcement_date: date
    attachment: Optional[str]


class ExamBase(SQLModel):
    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime


class AssignmentBase(SQLModel):
    id: uuid.UUID
    title: str
    start_date: date
    due_date: date
    pdf_name: str


class ResultBase(SQLModel):
    id: uuid.UUID
    score: float


class AttendanceBase(SQLModel):
    id: uuid.UUID
    attendance_date: datetime
    present: bool


# ===================== Read Schemas (with relations) =====================
class SaveResponse(SQLModel):
    id: str = Field(..., description="Resource id (stringified UUID)")
    message: str = Field(..., description="Human-friendly status message")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "c9b1d6b8-1f2b-4f3a-9f4b-1234567890ab",
                "message": "Saved successfully"
            }
        }


class ClassRead(ClassBase):
    supervisor: Optional[TeacherBase] = None
    grade: Optional[GradeBase] = None


class PaginatedClassResponse(PaginatedBaseResponse):
    data: List[ClassRead]


class ClassSave(SQLModel):
    name: str
    capacity: int
    supervisorId: Optional[uuid.UUID] = None
    gradeId: uuid.UUID


class ClassUpdateBase(ClassSave):
    id: uuid.UUID


class ClassDeleteResponse(SQLModel):
    id: str
    message: str
    lessons_affected: int
    students_affected: int
    events_affected: int
    announcements_affected: int


class TeacherRead(TeacherBase):
    subjects: List[SubjectBase] = []
    classes: List[ClassBase] = []
    lessons: List[LessonBase] = []


class PaginatedTeacherResponse(PaginatedBaseResponse):
    data: List[TeacherRead]


class TeacherDeleteResponse(SaveResponse):
    subject_affected: Optional[int] = Field(
        default=None,
        description="Number of subjects linked to this teacher"
    )
    lesson_affected: Optional[int] = Field(
        default=None,
        description="Number of lessons affected when modifying/deleting the teacher"
    )
    class_affected: Optional[int] = Field(
        default=None,
        description="Number of classes impacted (where teacher was supervisor)"
    )

    class Config(SaveResponse.Config):
        json_schema_extra = {
            "example": {
                "id": "c9b1d6b8-1f2b-4f3a-9f4b-1234567890ab",
                "message": "Teacher created successfully",
                "subject_affected": 3,
                "lesson_affected": 0,
                "class_affected": 1
            }
        }


class ParentRead(ParentBase):
    students: List[StudentBase] = []


class PaginatedParentResponse(PaginatedBaseResponse):
    data: List[ParentRead]


class SubjectRead(SubjectBase):
    teachers: List[TeacherBase] = []


class PaginatedSubjectResponse(PaginatedBaseResponse):
    data: List[SubjectRead]


class StudentRead(StudentBase):
    parent: Optional[ParentBase] = None
    related_class: Optional[ClassBase] = None
    grade: Optional[GradeBase] = None


class PaginatedStudentResponse(PaginatedBaseResponse):
    data: List[StudentRead]


class StudentSave(SQLModel):
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    address: str
    img: Optional[str] = None
    blood_type: str
    sex: UserSex
    dob: date
    parent_id: uuid.UUID
    class_id: uuid.UUID
    grade_id: uuid.UUID


class StudentUpdateBase(StudentSave):
    id: uuid.UUID


class StudentDeleteResponse(SaveResponse):
    parent_removed: int = 0
    class_removed: int = 0
    grade_removed: int = 0
    attendance_affected: int = 0
    result_affected: int = 0


class SubjectSave(SQLModel):
    name: str
    teachersList: List[uuid.UUID]


class SubjectUpdateBase(SubjectSave):
    id: uuid.UUID


class SubjectSaveResponse(SaveResponse):
    lessons_affected: int | None


class LessonRead(LessonBase):
    teacher: Optional[TeacherBase] = None


class PaginatedLessonResponse(PaginatedBaseResponse):
    data: List[LessonRead]


class LessonSave(SQLModel):
    name: str
    day: Day
    start_time: datetime
    end_time: datetime

    subject_id: uuid.UUID
    class_id: uuid.UUID
    teacher_id: uuid.UUID


class LessonUpdate(LessonSave):
    id: uuid.UUID


class LessonDeleteResponse(SaveResponse):
    exam_affected: int = 0
    assignment_affected: int = 0
    attendance_affected: int = 0


class EventRead(EventBase):
    related_class: Optional[ClassBase] = None


class EventSave(SQLModel):
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    class_id: Optional[uuid.UUID] = None


class EventUpdate(EventSave):
    id: uuid.UUID


class PaginatedEventResponse(PaginatedBaseResponse):
    data: List[EventRead]


class AnnouncementRead(AnnouncementBase):
    related_class: Optional[ClassBase] = None


class PaginatedAnnouncementResponse(PaginatedBaseResponse):
    data: List[AnnouncementRead]


class AnnouncementSave(SQLModel):
    title: str
    description: str
    announcement_date: date
    class_id: Optional[uuid.UUID] = None


class AnnouncementUpdate(AnnouncementSave):
    id: uuid.UUID


class ExamRead(ExamBase):
    lesson: Optional[LessonRead] = None


class PaginatedExamResponse(PaginatedBaseResponse):
    data: List[ExamRead]


class ExamSave(SQLModel):
    title: str
    start_time: datetime
    end_time: datetime
    lesson_id: uuid.UUID


class ExamUpdate(ExamSave):
    id: uuid.UUID


class ExamDeleteResponse(SaveResponse):
    result_affected: int = 0


class AssignmentRead(AssignmentBase):
    lesson: Optional[LessonRead] = None


class PaginatedAssignmentResponse(PaginatedBaseResponse):
    data: List[AssignmentRead]


class AssignmentSave(SQLModel):
    title: str
    start_date: date
    end_date: date
    lesson_id: uuid.UUID


class AssignmentUpdate(AssignmentSave):
    id: uuid.UUID


class AssignmentDeleteResponse(SaveResponse):
    result_affected: int = 0


class ResultRead(ResultBase):
    exam: Optional[ExamRead] = None
    assignment: Optional[AssignmentRead] = None
    student: Optional[StudentBase] = None


class PaginatedResultResponse(PaginatedBaseResponse):
    data: List[ResultRead]


class ResultSave(SQLModel):
    score: float = 0
    exam_id: Optional[uuid.UUID] | None
    assignment_id: Optional[uuid.UUID] | None
    student_id: uuid.UUID


class ResultUpdate(ResultSave):
    id: uuid.UUID


class ParentSave(SQLModel):
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    address: str
    password: str | None


class ParentUpdate(ParentSave):
    id: uuid.UUID


class AttendanceRead(AttendanceBase):
    student: Optional[StudentBase] = None
    lesson: Optional[LessonBase] = None


class AttendanceRecord(SQLModel):
    student_id: uuid.UUID
    present: bool = False


class AttendanceBulkSave(SQLModel):
    lesson_id: uuid.UUID
    attendance_date: date
    attendances: List[AttendanceRecord]

    @field_validator('attendances')
    def validate_attendances_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one attendance record is required.")
        return v


class AttendanceSave(AttendanceRecord):
    lesson_id: uuid.UUID
    attendance_date: date


class AttendanceUpdate(SQLModel):
    id: uuid.UUID
    present: bool


class AttendanceSaveResponse(SQLModel):
    id: str
    message: str


class AttendanceBulkSaveResponse(SQLModel):
    message: str
    total_saved: int
    failed: List[dict] = []


class AttendanceDetail(SQLModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    lesson_id: uuid.UUID
    lesson_name: str
    attendance_date: date
    present: bool
    is_delete: bool


class AttendanceListResponse(SQLModel):
    attendances: List[AttendanceDetail]
    total: int


class CountStudent(SQLModel):
    boys: int
    girls: int


class UsersCount(SQLModel):
    admins: int
    teachers: int
    students: CountStudent
    parents: int


# ===================== Attendance Dashboard & Summary Schemas =====================

class AttendanceDashboardSummary(SQLModel):
    """Admin dashboard summary for a specific date"""
    date: date
    total_classes: int
    classes_with_attendance: int
    pending_classes: int
    total_students: int
    present_count: int
    absent_count: int
    attendance_rate: float  # Percentage


class ClassAttendanceSummary(SQLModel):
    """Class-level attendance summary"""
    class_id: uuid.UUID
    class_name: str
    grade_level: Optional[int] = None
    total_students: int
    present_count: int
    absent_count: int
    not_marked_count: int
    attendance_rate: float  # Percentage
    has_attendance: bool  # Whether attendance was taken for this class


class ClasswiseAttendanceResponse(SQLModel):
    """Response for class-wise attendance summary"""
    date: date
    classes: List[ClassAttendanceSummary]
    total_classes: int


class StudentAttendanceRecord(SQLModel):
    """Individual attendance record for a student"""
    id: uuid.UUID
    date: date
    present: bool
    lesson_id: uuid.UUID
    lesson_name: str
    subject_name: Optional[str] = None


class StudentMonthlyAttendance(SQLModel):
    """Monthly attendance for a single student"""
    student_id: uuid.UUID
    student_name: str
    month: int
    year: int
    total_days: int
    present_days: int
    absent_days: int
    attendance_rate: float
    records: List[StudentAttendanceRecord]


class CalendarDayData(SQLModel):
    """Attendance data for a single day (for calendar heatmap)"""
    date: date
    present_count: int
    absent_count: int
    total_records: int
    attendance_rate: float  # 0-100


class CalendarHeatmapResponse(SQLModel):
    """Response for calendar heatmap view"""
    student_id: Optional[uuid.UUID] = None
    student_name: Optional[str] = None
    month: int
    year: int
    days: List[CalendarDayData]
    monthly_summary: dict  # Overall monthly stats


class ClassStudentAttendance(SQLModel):
    """Student attendance status within a class for a specific date"""
    student_id: uuid.UUID
    student_name: str
    username: str
    attendance_id: Optional[uuid.UUID] = None
    present: Optional[bool] = None  # None means not marked yet
    marked_at: Optional[datetime] = None


class ClassAttendanceDetailResponse(SQLModel):
    """Detailed attendance for a specific class on a specific date"""
    class_id: uuid.UUID
    class_name: str
    date: date
    lesson_id: Optional[uuid.UUID] = None
    lesson_name: Optional[str] = None
    total_students: int
    present_count: int
    absent_count: int
    not_marked_count: int
    students: List[ClassStudentAttendance]


class TeacherClassSummary(SQLModel):
    """Class summary for teacher's view"""
    class_id: uuid.UUID
    class_name: str
    lesson_id: uuid.UUID
    lesson_name: str
    subject_name: Optional[str] = None
    day: str
    total_students: int
    attendance_marked: bool
    present_count: int
    absent_count: int


# ===================== Take Attendance Workflow Schemas =====================

class StudentRosterItem(SQLModel):
    """Student item in the attendance roster"""
    student_id: uuid.UUID
    student_name: str
    username: str
    img: Optional[str] = None
    # Existing attendance info (if any)
    attendance_id: Optional[uuid.UUID] = None
    present: Optional[bool] = None  # None = not marked, True/False = marked


class LessonRosterResponse(SQLModel):
    """Response for getting lesson roster for taking attendance"""
    lesson_id: uuid.UUID
    lesson_name: str
    class_id: uuid.UUID
    class_name: str
    subject_name: Optional[str] = None
    target_date: date
    total_students: int
    attendance_exists: bool  # True if attendance already taken for this date
    marked_count: int
    students: List[StudentRosterItem]


class LessonForDateItem(SQLModel):
    """Lesson item for a specific date (used in LessonSelector)"""
    lesson_id: uuid.UUID
    lesson_name: str
    class_id: uuid.UUID
    class_name: str
    subject_id: Optional[uuid.UUID] = None
    subject_name: Optional[str] = None
    teacher_id: Optional[uuid.UUID] = None
    teacher_name: Optional[str] = None
    start_time: datetime
    end_time: datetime
    day: str
    attendance_status: str  # "not_taken", "partial", "complete"
    students_count: int
    present_count: int
    absent_count: int


class LessonsForDateResponse(SQLModel):
    """Response for getting lessons for a specific date"""
    date: date
    day_of_week: str
    total_lessons: int
    lessons: List[LessonForDateItem]


class AttendanceTakeRequest(SQLModel):
    """Request body for taking/updating attendance in bulk"""
    lesson_id: uuid.UUID
    attendance_date: date
    records: List[AttendanceRecord]
    overwrite_existing: bool = False  # If True, update existing records; if False, reject if exists

    @field_validator('records')
    def validate_records_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one attendance record is required.")
        return v


class AttendanceTakeResponse(SQLModel):
    """Response for taking attendance"""
    message: str
    lesson_id: uuid.UUID
    attendance_date: date
    total_students: int
    created_count: int
    updated_count: int
    present_count: int
    absent_count: int
