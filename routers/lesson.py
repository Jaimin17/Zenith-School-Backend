import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.lesson import getAllLessonIsDeleteFalse, getAllLessonOfTeacherIsDeleteFalse, \
    getAllLessonOfClassIsDeleteFalse
from schemas import LessonRead

router = APIRouter(
    prefix="/lesson",
)

@router.get("/getAll", response_model=List[LessonRead])
def getAllLesson(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_lessons = getAllLessonIsDeleteFalse(session, search, page)
    return all_lessons

@router.get("/teacher/{teacherId}", response_model=List[LessonRead])
def getAllLessonOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_lessons = getAllLessonOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_lessons

@router.get("/class/{classId}", response_model=List[LessonRead])
def getAllLessonOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_lessons = getAllLessonOfClassIsDeleteFalse(classId, session, search, page)
    return all_lessons