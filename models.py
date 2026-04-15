from datetime import datetime, date, time
from enum import Enum
import uuid
from typing import Optional, List, TYPE_CHECKING

from pydantic import EmailStr
from sqlalchemy import JSON, Column, Enum as SAEnum
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    pass


# ===================== Base User =====================
class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, nullable=False)
    first_name: str = Field(nullable=False)
    last_name: str = Field(nullable=False)
    email: EmailStr = Field(unique=True, nullable=False)
    password: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    is_superuser: bool = Field(default=False, nullable=False)

    model_config = {
        "arbitrary_types_allowed": True,
        "from_attributes": True,
    }


class Admin(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, nullable=False)
    password: str = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


# ===================== Enums =====================
class UserSex(str, Enum):
    MALE = "male"
    FEMALE = "female"


class Day(str, Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class StudentStatus(str, Enum):
    ACTIVE = "active"
    GRADUATED = "graduated"
    INACTIVE = "inactive"


# ===================== Parent =====================
class Parent(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, nullable=False)
    first_name: str = Field(nullable=False)
    last_name: str = Field(nullable=False)
    email: EmailStr = Field(unique=True, nullable=False)
    phone: str = Field(nullable=False, unique=True)
    address: str = Field(nullable=False, min_length=5)
    password: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    students: List["Student"] = Relationship(back_populates="parent")


# ===================== Grade =====================
class Grade(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    level: int = Field(nullable=False, unique=True)
    is_delete: bool = Field(default=False, nullable=False)

    students: List["Student"] = Relationship(back_populates="grade")
    classes: List["Class"] = Relationship(back_populates="grade")


# ===================== AcademicYear =====================
class AcademicYear(SQLModel, table=True):
    __tablename__ = "academic_year"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    year_label: str = Field(nullable=False, unique=True)  # e.g. "2025-2026"
    start_date: date = Field(nullable=False)
    end_date: date = Field(nullable=False)
    is_active: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)

    class_histories: List["StudentClassHistory"] = Relationship(back_populates="academic_year")
    lessons: List["Lesson"] = Relationship(back_populates="academic_year")


# ===================== Association Tables =====================
class TeacherSubjectLink(SQLModel, table=True):
    __tablename__ = "teacher_subject_link"

    teacher_id: uuid.UUID = Field(foreign_key="teacher.id", primary_key=True)
    subject_id: uuid.UUID = Field(foreign_key="subject.id", primary_key=True)


# ===================== Teacher =====================
class Teacher(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, nullable=False)
    first_name: str = Field(nullable=False)
    last_name: str = Field(nullable=False)
    email: EmailStr = Field(unique=True, nullable=False)
    phone: str = Field(nullable=False, unique=True)
    address: str = Field(nullable=False, min_length=5)
    img: Optional[str] = Field(default=None)
    blood_type: str = Field(nullable=False)
    sex: UserSex = Field(nullable=False)
    dob: date = Field(default_factory=datetime.now, nullable=False)
    password: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    subjects: List["Subject"] = Relationship(back_populates="teachers", link_model=TeacherSubjectLink)
    lessons: List["Lesson"] = Relationship(back_populates="teacher")
    classes: List["Class"] = Relationship(back_populates="supervisor")


# ===================== Subject =====================
class Subject(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    teachers: List["Teacher"] = Relationship(back_populates="subjects", link_model=TeacherSubjectLink)
    lessons: List["Lesson"] = Relationship(back_populates="subject")


# ===================== Event / Announcement =====================
class Event(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    img: Optional[List[str]] = Field(default=None, sa_column=Column(JSON, nullable=True))
    start_time: datetime = Field(nullable=False)
    end_time: datetime = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    related_class: Optional["Class"] = Relationship(back_populates="events")


class Announcement(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    announcement_date: date = Field(default_factory=date.today, nullable=False)
    attachment: Optional[str] = Field(default=None)
    is_delete: bool = Field(default=False, nullable=False)

    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    related_class: Optional["Class"] = Relationship(back_populates="announcements")


# ===================== Class =====================
class Class(SQLModel, table=True):
    __tablename__ = "class"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(nullable=False, unique=True)
    capacity: int = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    supervisor_id: Optional[uuid.UUID] = Field(default=None, foreign_key="teacher.id")
    supervisor: Optional["Teacher"] = Relationship(back_populates="classes")

    lessons: List["Lesson"] = Relationship(back_populates="related_class")
    students: List["Student"] = Relationship(back_populates="related_class")

    grade_id: Optional[uuid.UUID] = Field(default=None, foreign_key="grade.id")
    grade: Optional["Grade"] = Relationship(back_populates="classes")

    events: List["Event"] = Relationship(back_populates="related_class")
    announcements: List["Announcement"] = Relationship(back_populates="related_class")
    attendances: List["Attendance"] = Relationship(back_populates="related_class")


# ===================== Student =====================
class Student(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, nullable=False)
    first_name: str = Field(nullable=False)
    last_name: str = Field(nullable=False)
    email: EmailStr = Field(unique=True, nullable=False)
    phone: Optional[str] = Field(default=None)
    address: str = Field(nullable=False, min_length=5)
    img: Optional[str] = Field(default=None)
    blood_type: str = Field(nullable=False)
    sex: UserSex = Field(nullable=False)
    dob: date = Field(default_factory=datetime.now, nullable=False)
    password: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)
    status: StudentStatus = Field(
        default=StudentStatus.ACTIVE,
        sa_column=Column(
            SAEnum(StudentStatus, values_callable=lambda x: [e.value for e in x], name="studentstatus"),
            nullable=False,
            default=StudentStatus.ACTIVE,
        )
    )

    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="parent.id")
    parent: Optional["Parent"] = Relationship(back_populates="students")

    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    related_class: Optional["Class"] = Relationship(back_populates="students")

    grade_id: Optional[uuid.UUID] = Field(default=None, foreign_key="grade.id")
    grade: Optional["Grade"] = Relationship(back_populates="students")

    attendances: List["Attendance"] = Relationship(back_populates="student")
    results: List["Result"] = Relationship(back_populates="student")
    testimonials: Optional["Testimonials"] = Relationship(back_populates="student")
    class_histories: List["StudentClassHistory"] = Relationship(back_populates="student")


# ===================== StudentClassHistory =====================
class StudentClassHistory(SQLModel, table=True):
    __tablename__ = "student_class_history"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)

    student_id: uuid.UUID = Field(nullable=False, foreign_key="student.id")
    student: "Student" = Relationship(back_populates="class_histories")

    academic_year_id: uuid.UUID = Field(nullable=False, foreign_key="academic_year.id")
    academic_year: "AcademicYear" = Relationship(back_populates="class_histories")

    # Snapshot of the class/grade the student was in for this year (nullable = unassigned)
    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    grade_id: Optional[uuid.UUID] = Field(default=None, foreign_key="grade.id")


# ===================== Lesson =====================
class Lesson(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(nullable=False)
    day: Day = Field(nullable=False)
    start_time: time = Field(nullable=False)
    end_time: time = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    subject_id: Optional[uuid.UUID] = Field(default=None, foreign_key="subject.id")
    subject: Optional["Subject"] = Relationship(back_populates="lessons")

    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    related_class: Optional["Class"] = Relationship(back_populates="lessons")

    teacher_id: Optional[uuid.UUID] = Field(default=None, foreign_key="teacher.id")
    teacher: Optional["Teacher"] = Relationship(back_populates="lessons")

    academic_year_id: Optional[uuid.UUID] = Field(default=None, foreign_key="academic_year.id")
    academic_year: Optional["AcademicYear"] = Relationship(back_populates="lessons")

    exams: List["Exam"] = Relationship(back_populates="lesson")
    assignments: List["Assignment"] = Relationship(back_populates="lesson")


# ===================== Exam / Assignment =====================
class Exam(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    start_time: datetime = Field(nullable=False)
    end_time: datetime = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    lesson_id: Optional[uuid.UUID] = Field(default=None, foreign_key="lesson.id")
    lesson: Optional["Lesson"] = Relationship(back_populates="exams")

    results: List["Result"] = Relationship(back_populates="exam")


class Assignment(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    start_date: date = Field(nullable=False)
    due_date: date = Field(nullable=False)
    pdf_name: str = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    lesson_id: Optional[uuid.UUID] = Field(default=None, foreign_key="lesson.id")
    lesson: Optional["Lesson"] = Relationship(back_populates="assignments")

    results: List["Result"] = Relationship(back_populates="assignment")


# ===================== Result / Attendance =====================
class Result(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    score: float = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    exam_id: Optional[uuid.UUID] = Field(default=None, foreign_key="exam.id")
    exam: Optional["Exam"] = Relationship(back_populates="results")

    assignment_id: Optional[uuid.UUID] = Field(default=None, foreign_key="assignment.id")
    assignment: Optional["Assignment"] = Relationship(back_populates="results")

    student_id: uuid.UUID = Field(nullable=False, foreign_key="student.id")
    student: Student = Relationship(back_populates="results")


class Attendance(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    attendance_date: datetime = Field(default_factory=datetime.now, nullable=False)
    present: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    student_id: Optional[uuid.UUID] = Field(default=None, foreign_key="student.id")
    student: Optional["Student"] = Relationship(back_populates="attendances")

    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    related_class: Optional["Class"] = Relationship(back_populates="attendances")

class Holiday(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    date: datetime = Field(nullable=False, unique=True)
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None)


class BlacklistToken(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(nullable=False)
    access_token: str = Field(nullable=False)
    refresh_token: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)


class Banner(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    img: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_active: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


class PhotoGallery(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    img: str = Field(nullable=False)
    is_sport: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_active: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


class Testimonials(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rating: float = Field(default=5, nullable=False, max_items=5, min_items=1)
    description: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)

    student_id: uuid.UUID = Field(nullable=False, foreign_key="student.id")
    student: Student = Relationship(back_populates="testimonials")

    is_active: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


class Achievements(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    img: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_active: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


class SportsPrograms(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    img: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_active: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


class JobOpenings(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    experience: int = Field(default=0, nullable=False)
    positions: int = Field(default=1, nullable=False)
    location: Optional[str] = Field(default=None)
    salary_range: Optional[str] = Field(default=None)
    deadline: Optional[date] = Field(default=None)
    job_type: JobType = Field(default=JobType.FULL_TIME, nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)

    subject_id: Optional[uuid.UUID] = Field(default=None, foreign_key="subject.id")

    jobApplications: List["JobApplications"] = Relationship(back_populates="jobOpenings")

    is_active: bool = Field(default=True, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


class JobApplications(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(nullable=False)
    email: str = Field(nullable=False)
    phone: str = Field(nullable=False)
    location: str = Field(nullable=False)
    portfolio_link: Optional[str] = Field(default=None)

    jobOpening_id: uuid.UUID = Field(nullable=False, foreign_key="jobopenings.id")
    jobOpenings: "JobOpenings" = Relationship(back_populates="jobApplications")

    about_applicant: str = Field(nullable=False)
    resume: str = Field(nullable=False)
    status: ApplicationStatus = Field(default=ApplicationStatus.PENDING, nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)

    is_reviewed: bool = Field(default=False, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)


class ChatbotTelemetryLog(SQLModel, table=True):
    __tablename__ = "chatbot_telemetry_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False, index=True)
    request_id: str = Field(nullable=False, index=True)
    event: str = Field(nullable=False, index=True)
    level: str = Field(default="INFO", nullable=False)
    source: str = Field(default="chatbot", nullable=False)
    payload_json: dict = Field(sa_column=Column(JSON, nullable=False))
    hash_key: str = Field(nullable=False, index=True)
    is_delete: bool = Field(default=False, nullable=False)


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_session"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(nullable=False, index=True)
    owner_role: str = Field(nullable=False, index=True)
    title: str = Field(default="New Chat", nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=datetime.now, nullable=False, index=True)
    is_delete: bool = Field(default=False, nullable=False)

    messages: List["ChatMessage"] = Relationship(back_populates="session")


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(nullable=False, foreign_key="chat_session.id", index=True)
    role: str = Field(nullable=False)
    content: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False, index=True)

    session: "ChatSession" = Relationship(back_populates="messages")
