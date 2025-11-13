import uuid
from typing import List

from fastapi import APIRouter
from deps import CurrentUser
from core.database import SessionDep
from schemas import StudentRead
from repository.student import getAllStudentsIsDeleteFalse, getAllStudentsOfTeacherAndIsDeleteFalse

router = APIRouter(
    prefix="/student",
)

@router.get("/getAll", response_model=List[StudentRead])
def getAllStudents(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_students = getAllStudentsIsDeleteFalse(session, search, page)
    return all_students

@router.get("/{teacherId}", response_model=List[StudentRead])
def getStudentByTeacherId(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_students = getAllStudentsOfTeacherAndIsDeleteFalse(session, teacherId, search, page)
    return all_students