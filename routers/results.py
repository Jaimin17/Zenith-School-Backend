import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.results import getAllResultsIsDeleteFalse, getAllResultsByTeacherIsDeleteFalse, \
    getAllResultsOfClassIsDeleteFalse, getAllResultsOfStudentIsDeleteFalse
from schemas import ResultRead

router = APIRouter(
    prefix="/results",
)

@router.get("/getAll", response_model=List[ResultRead])
def getAllResults(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_results = getAllResultsIsDeleteFalse(session, search, page)
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