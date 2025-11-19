import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser, TeacherOrAdminUser
from repository.classes import getAllClassesIsDeleteFalse, getAllClassOfTeacherAndIsDeleteFalse
from schemas import ClassRead

router = APIRouter(
    prefix="/classes",
)

@router.get("/getAll", response_model=List[ClassRead])
def getAllClasses(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_classes = getAllClassesIsDeleteFalse(session, search, page)
    else:
        all_classes = getAllClassOfTeacherAndIsDeleteFalse(user.id, session, search, page)
    return all_classes

@router.get("/{supervisorId}", response_model=List[ClassRead])
def getClassesOfTeacher(supervisorId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    teacher_class = getAllClassOfTeacherAndIsDeleteFalse(supervisorId, session, search, page)
    return teacher_class