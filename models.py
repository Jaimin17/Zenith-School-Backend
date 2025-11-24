from datetime import datetime, date
from enum import Enum
import uuid
from typing import Optional, List, TYPE_CHECKING

from pydantic import EmailStr
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

    students: List["Student"] = Relationship(back_populates="grade")
    classes: List["Class"] = Relationship(back_populates="grade")


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
    password: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="parent.id")
    parent: Optional["Parent"] = Relationship(back_populates="students")

    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    related_class: Optional["Class"] = Relationship(back_populates="students")

    grade_id: Optional[uuid.UUID] = Field(default=None, foreign_key="grade.id")
    grade: Optional["Grade"] = Relationship(back_populates="students")

    attendances: List["Attendance"] = Relationship(back_populates="student")
    results: List["Result"] = Relationship(back_populates="student")


# ===================== Lesson =====================
class Lesson(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(nullable=False)
    day: Day = Field(nullable=False)
    start_time: datetime = Field(nullable=False)
    end_time: datetime = Field(nullable=False)
    is_delete: bool = Field(default=False, nullable=False)

    subject_id: Optional[uuid.UUID] = Field(default=None, foreign_key="subject.id")
    subject: Optional["Subject"] = Relationship(back_populates="lessons")

    class_id: Optional[uuid.UUID] = Field(default=None, foreign_key="class.id")
    related_class: Optional["Class"] = Relationship(back_populates="lessons")

    teacher_id: Optional[uuid.UUID] = Field(default=None, foreign_key="teacher.id")
    teacher: Optional["Teacher"] = Relationship(back_populates="lessons")

    exams: List["Exam"] = Relationship(back_populates="lesson")
    assignments: List["Assignment"] = Relationship(back_populates="lesson")
    attendances: List["Attendance"] = Relationship(back_populates="lesson")


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
    start_date: date = Field(nullable=False)
    due_date: date = Field(nullable=False)
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

    student_id: Optional[uuid.UUID] = Field(default=None, foreign_key="student.id")
    student: Optional["Student"] = Relationship(back_populates="results")


class Attendance(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    attendance_date: datetime = Field(default_factory=datetime.now, nullable=False)
    present: bool = Field(default=False, nullable=False)

    student_id: Optional[uuid.UUID] = Field(default=None, foreign_key="student.id")
    student: Optional["Student"] = Relationship(back_populates="attendances")

    lesson_id: Optional[uuid.UUID] = Field(default=None, foreign_key="lesson.id")
    lesson: Optional["Lesson"] = Relationship(back_populates="attendances")