import uuid
from datetime import datetime, date
from typing import List, Optional

from fastapi import Form
from pydantic import EmailStr, BaseModel, field_validator, ConfigDict
from sqlmodel import SQLModel, Field

from models import UserSex, Day


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


class SubjectRead(SubjectBase):
    teachers: List[TeacherBase] = []


class SubjectUpdateBase(SQLModel):
    id: uuid.UUID
    name: str
    teachersList: List[uuid.UUID]


class StudentRead(StudentBase):
    parent: Optional[ParentBase] = None
    related_class: Optional[ClassBase] = None
    grade: Optional[GradeBase] = None


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


class SubjectSaveResponse(SaveResponse):
    lessons_affected: int | None


class LessonRead(LessonBase):
    teacher: Optional[TeacherBase] = None


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


class AnnouncementRead(AnnouncementBase):
    related_class: Optional[ClassBase] = None


class AnnouncementSave(SQLModel):
    title: str
    description: str
    announcement_date: date
    class_id: Optional[uuid.UUID]


class AnnouncementUpdate(AnnouncementSave):
    id: uuid.UUID


class ExamRead(ExamBase):
    lesson: Optional[LessonRead] = None


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


class UsersCount(SQLModel):
    admins: int
    teachers: int
    students: int
    parents: int