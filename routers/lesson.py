import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, StudentOrTeacherOrAdminUser, AdminUser, ParentUser
from models import Day
from repository.lesson import getAllLessonIsDeleteFalse, getAllLessonOfTeacherIsDeleteFalse, \
    getAllLessonOfClassIsDeleteFalse, getAllLessonOfParentIsDeleteFalse, countAllLessonOfTeacher, \
    countAllLessonOfStudent, lessonSave, lessonUpdate, lessonSoftDelete, getLessonById, \
    getAllLessonOfCurrentWeekIsDeleteFalse, getAllLessonOfTeacherOfCurrentWeekIsDeleteFalse, \
    getAllLessonOfClassOfCurrentWeekIsDeleteFalse, getAllLessonOfStudentOfCurrentWeekIsDeleteFalse
from schemas import LessonRead, SaveResponse, LessonSave, LessonUpdate, LessonDeleteResponse, PaginatedLessonResponse
from datetime import datetime, date, timedelta

router = APIRouter(
    prefix="/lesson",
)


@router.get("/getAll", response_model=PaginatedLessonResponse)
def getAllLesson(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_lessons = getAllLessonIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_lessons = getAllLessonOfTeacherIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_lessons = getAllLessonOfClassIsDeleteFalse(user.class_id, session, search, page)
        all_lessons = getAllLessonOfClassIsDeleteFalse(user.class_id, session, search, page)
    else:
        all_lessons = getAllLessonOfParentIsDeleteFalse(user.id, session, search, page)
    return all_lessons


@router.get("/getAllOfCurrentWeek", response_model=List[LessonRead])
def getAllOfCurrentWeek(current_user: StudentOrTeacherOrAdminUser, session: SessionDep):
    user, role = current_user

    today: date = date.today()

    days_since_monday: int = today.weekday()
    days_until_friday: int = 4 - today.weekday()

    monday: date = today - timedelta(days=days_since_monday)
    friday: date = today + timedelta(days=days_until_friday)

    week_start: datetime = datetime.combine(monday, datetime.min.time())
    week_end: datetime = datetime.combine(friday, datetime.max.time())

    if role == "admin":
        all_lessons = getAllLessonOfCurrentWeekIsDeleteFalse(session, week_start, week_end)
    elif role == "teacher":
        all_lessons = getAllLessonOfTeacherOfCurrentWeekIsDeleteFalse(user.id, session, week_start, week_end)
    else:
        all_lessons = getAllLessonOfClassOfCurrentWeekIsDeleteFalse(user.class_id, session, week_start, week_end)

    return all_lessons


@router.get("/getLessonForStudent/{studentId}", response_model=List[LessonRead])
def getLessonForStudent(studentId: uuid.UUID, current_user: AllUser, session: SessionDep):
    user, role = current_user

    today: date = date.today()

    days_since_monday: int = today.weekday()
    days_until_friday: int = 4 - today.weekday()

    monday: date = today - timedelta(days=days_since_monday)
    friday: date = today + timedelta(days=days_until_friday)

    week_start: datetime = datetime.combine(monday, datetime.min.time())
    week_end: datetime = datetime.combine(friday, datetime.max.time())

    all_lessons = getAllLessonOfStudentOfCurrentWeekIsDeleteFalse(studentId, user, role, session, week_start, week_end)

    return all_lessons


@router.get("/getById/{lessonId}", response_model=LessonRead)
def getById(lessonId: uuid.UUID, current_user: AllUser, session: SessionDep):
    user, role = current_user

    lesson_detail = getLessonById(lessonId, session)

    if not lesson_detail:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found with provided ID."
        )

    if role.lower() == "admin":
        return lesson_detail

    elif role.lower() == "teacher":
        if lesson_detail.teacher_id and lesson_detail.teacher_id == user.id:
            return lesson_detail
        elif lesson_detail.related_class and lesson_detail.related_class.supervisor_id == user.id:
            return lesson_detail
        else:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this Lesson."
            )

    elif role.lower() == "student":
        if lesson_detail.related_class is None:
            raise HTTPException(
                status_code=500,
                detail="Lesson class data is missing."
            )

        class_students = [s.id for s in lesson_detail.related_class.students if not s.is_delete]
        if user.id not in class_students:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this lesson."
            )

        return lesson_detail

    elif role.lower() == "parent":
        if lesson_detail.related_class is None:
            raise HTTPException(
                status_code=500,
                detail="Lesson class data is missing."
            )

        if not user.students:
            raise HTTPException(
                status_code=403,
                detail="No students associated with your account."
            )

        class_student_ids = [s.id for s in lesson_detail.related_class.students if not s.is_delete]
        parent_student_ids = [s.id for s in user.students if not s.is_delete]

        # Check if any of parent's students are in the class
        has_access = any(student_id in class_student_ids for student_id in parent_student_ids)

        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="None of your children have access to this lesson."
            )

        return lesson_detail

    else:
        raise HTTPException(
            status_code=403,
            detail="Invalid user role."
        )


@router.get("/teacher/{teacherId}", response_model=PaginatedLessonResponse)
def getLessonOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                       page: int = 1):
    all_lessons = getAllLessonOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_lessons


@router.get("/teacher/weekly/{teacherId}", response_model=List[LessonRead])
def getAllLessonOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    all_lessons = getAllLessonOfTeacherIsDeleteFalse(teacherId, session, None, 1, False)
    return all_lessons


@router.get("/countByTeacher/{teacherId}", response_model=int)
def countLessonByTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    total_lessons = countAllLessonOfTeacher(teacherId, session)
    return total_lessons


@router.get("/countByStudent/{studentId}", response_model=int)
def countLessonByStudent(studentId: uuid.UUID, current_user: StudentOrTeacherOrAdminUser, session: SessionDep):
    total_lesson = countAllLessonOfStudent(studentId, session)
    return total_lesson


@router.get("/class/{classId}", response_model=PaginatedLessonResponse)
def getAllLessonOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                        page: int = 1):
    all_lessons = getAllLessonOfClassIsDeleteFalse(classId, session, search, page)
    return all_lessons


@router.post("/save", response_model=SaveResponse)
def saveLesson(lesson: LessonSave, current_user: AdminUser, session: SessionDep):
    if not lesson.name or len(lesson.name.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Lesson name is required and must be at least 3 characters long."
        )

    if not lesson.day or not isinstance(lesson.day, Day):
        raise HTTPException(
            status_code=400,
            detail="Day is required and must be a valid day of the week."
        )

    if not lesson.start_time:
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not lesson.end_time:
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if lesson.start_time >= lesson.end_time:
        raise HTTPException(
            status_code=400,
            detail="Lesson start time must be before end time."
        )

    if not lesson.subject_id:
        raise HTTPException(
            status_code=400,
            detail="Subject is required."
        )

    if not lesson.class_id:
        raise HTTPException(
            status_code=400,
            detail="Class is required."
        )

    if not lesson.teacher_id:
        raise HTTPException(
            status_code=400,
            detail="Teacher is required."
        )

    result = lessonSave(lesson, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateLesson(current_user: AdminUser, lesson: LessonUpdate, session: SessionDep):
    if not lesson.id:
        raise HTTPException(
            status_code=400,
            detail="Lesson ID is required for updating."
        )

    if not lesson.name or len(lesson.name.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Lesson name is required and must be at least 3 characters long."
        )

    if not lesson.day or not isinstance(lesson.day, Day):
        raise HTTPException(
            status_code=400,
            detail="Day is required and must be a valid day of the week."
        )

    if not lesson.start_time:
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not lesson.end_time:
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if lesson.start_time >= lesson.end_time:
        raise HTTPException(
            status_code=400,
            detail="Lesson start time must be before end time."
        )

    if not lesson.subject_id:
        raise HTTPException(
            status_code=400,
            detail="Subject is required."
        )

    if not lesson.class_id:
        raise HTTPException(
            status_code=400,
            detail="Class is required."
        )

    if not lesson.teacher_id:
        raise HTTPException(
            status_code=400,
            detail="Teacher is required."
        )

    result = lessonUpdate(lesson, session)
    return result


@router.delete("/delete", response_model=LessonDeleteResponse)
def softDeleteLesson(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Lesson ID is required for deleting."
        )

    result = lessonSoftDelete(id, session)
    return result
