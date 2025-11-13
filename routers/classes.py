import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.classes import getAllClassesIsDeleteFalse, getAllClassOfTeacherAndIsDeleteFalse
from schemas import ClassRead

router = APIRouter(
    prefix="/classes",
)

@router.get("/getAll", response_model=List[ClassRead])
def getAllClasses(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_classes = getAllClassesIsDeleteFalse(session, search, page)
    return all_classes

@router.get("/{supervisorId}", response_model=List[ClassRead])
def getTeacherByClassId(supervisorId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    teacher_class = getAllClassOfTeacherAndIsDeleteFalse(supervisorId, session, search, page)
    return teacher_class