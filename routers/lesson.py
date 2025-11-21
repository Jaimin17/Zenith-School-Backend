import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser, AllUser
from repository.lesson import getAllLessonIsDeleteFalse, getAllLessonOfTeacherIsDeleteFalse, \
    getAllLessonOfClassIsDeleteFalse, getAllLessonOfParentIsDeleteFalse
from schemas import LessonRead

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
def getAllLessonOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_lessons = getAllLessonOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_lessons

@router.get("/class/{classId}", response_model=List[LessonRead])
def getAllLessonOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_lessons = getAllLessonOfClassIsDeleteFalse(classId, session, search, page)
    return all_lessons