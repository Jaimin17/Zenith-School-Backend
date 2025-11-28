import uuid
from datetime import datetime, date
from typing import List, Optional

from pydantic import EmailStr, BaseModel
from sqlmodel import SQLModel

from models import UserSex, Day


class UserBase(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    is_active: bool
    is_superuser: bool

class RegisterUser(SQLModel):
    username: str
    firstName: str
    lastName: str
    email: EmailStr
    password: str

class UserPublic(SQLModel):
    id: uuid.UUID

class Token(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(SQLModel):
    refresh_token: str


class TokenPayload(SQLModel):
    sub: str # username
    role: str # role
    user_id: str # id
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


class ResultBase(SQLModel):
    id: uuid.UUID
    score: float


class AttendanceBase(SQLModel):
    id: uuid.UUID
    attendance_date: datetime
    present: bool


# ===================== Read Schemas (with relations) =====================

class ClassRead(ClassBase):
    supervisor: Optional[TeacherBase] = None
    grade: Optional[GradeBase] = None

class ClassSaveResponse(SQLModel):
    id: str
    message: str

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


class SubjectSave(SQLModel):
    name: str
    teachersList: List[uuid.UUID]


class SubjectSaveResponse(SQLModel):
    id: str
    message: str
    lessons_affected: int | None


class LessonRead(LessonBase):
    teacher: Optional[TeacherBase] = None


class EventRead(EventBase):
    related_class: Optional[ClassBase] = None


class AnnouncementRead(AnnouncementBase):
    related_class: Optional[ClassBase] = None


class ExamRead(ExamBase):
    lesson: Optional[LessonRead] = None


class AssignmentRead(AssignmentBase):
    lesson: Optional[LessonRead] = None


class ResultRead(ResultBase):
    exam: Optional[ExamRead] = None
    assignment: Optional[AssignmentRead] = None
    student: Optional[StudentBase] = None


class AttendanceRead(AttendanceBase):
    student: Optional[StudentBase] = None
    lesson: Optional[LessonBase] = None