import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, StudentOrTeacherOrAdminUser, AdminUser
from models import Day
from repository.lesson import getAllLessonIsDeleteFalse, getAllLessonOfTeacherIsDeleteFalse, \
    getAllLessonOfClassIsDeleteFalse, getAllLessonOfParentIsDeleteFalse, countAllLessonOfTeacher, \
    countAllLessonOfStudent, lessonSave, lessonUpdate, lessonSoftDelete
from schemas import LessonRead, StudentRead, SaveResponse, LessonSave, LessonUpdate, LessonDeleteResponse

router = APIRouter(
    prefix="/lesson",
)


@router.get("/getAll", response_model=List[LessonRead])
def getAllLesson(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_lessons = getAllLessonIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_lessons = getAllLessonOfTeacherIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_lessons = getAllLessonOfClassIsDeleteFalse(user.class_id, session, search, page)
    else:
        all_lessons = getAllLessonOfParentIsDeleteFalse(user.id, session, search, page)
    return all_lessons


@router.get("/teacher/{teacherId}", response_model=List[LessonRead])
def getAllLessonOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                          page: int = 1):
    all_lessons = getAllLessonOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_lessons


@router.get("/countByTeacher/{teacherId}", response_model=int)
def countLessonByTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    total_lessons = countAllLessonOfTeacher(teacherId, session)
    return total_lessons


@router.get("/countByStudent/{studentId}", response_model=int)
def countLessonByStudent(studentId: uuid.UUID, current_user: StudentOrTeacherOrAdminUser, session: SessionDep):
    total_lesson = countAllLessonOfStudent(studentId, session)
    return total_lesson


@router.get("/class/{classId}", response_model=List[LessonRead])
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
