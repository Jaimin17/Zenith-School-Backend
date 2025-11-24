import uuid
from typing import List

from fastapi import APIRouter
from deps import CurrentUser, TeacherOrAdminUser, AdminUser
from core.database import SessionDep
from repository.teacher import getAllTeachersIsDeleteFalse, getAllTeachersOfClassAndIsDeleteFalse, countTeacher
from schemas import TeacherRead

router = APIRouter(
    prefix="/teacher",
)

@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countTeacher(session)

@router.get("/getAll", response_model=List[TeacherRead])
def getAllTeachers(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    all_teachers = getAllTeachersIsDeleteFalse(session, search, page)
    return all_teachers

@router.get("/{classId}", response_model=List[TeacherRead])
def getTeacherByClassId(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_teachers = getAllTeachersOfClassAndIsDeleteFalse(classId, session, search, page)
    return all_teachers