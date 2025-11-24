import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser, AllUser
from repository.results import getAllResultsIsDeleteFalse, getAllResultsByTeacherIsDeleteFalse, \
    getAllResultsOfClassIsDeleteFalse, getAllResultsOfStudentIsDeleteFalse, getAllResultsOfParentIsDeleteFalse
from schemas import ResultRead

router = APIRouter(
    prefix="/results",
)

@router.get("/getAll", response_model=List[ResultRead])
def getAllResults(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_results = getAllResultsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_results = getAllResultsByTeacherIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_results = getAllResultsOfStudentIsDeleteFalse(user.id, session, search, page)
    elif role == "parent":
        all_results = getAllResultsOfParentIsDeleteFalse(user.id, session, search, page)
    return all_results

@router.get("/teacher/{teacherId}", response_model=List[ResultRead])
def getAllResultsByTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_results = getAllResultsByTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_results

@router.get("/class/{classId}", response_model=List[ResultRead])
def getAllResultsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_results = getAllResultsOfClassIsDeleteFalse(classId, session, search, page)
    return all_results

@router.get("/student/{studentId}", response_model=List[ResultRead])
def getAllResultsOfStudent(studentId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_results = getAllResultsOfStudentIsDeleteFalse(studentId, session, search, page)
    return all_results