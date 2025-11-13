import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.exams import getAllExamsIsDeleteFalse, getAllExamsOfTeacherIsDeleteFalse, \
    getAllExamsOfClassIsDeleteFalse
from schemas import ExamRead

router = APIRouter(
    prefix="/exam",
)

@router.get("/getAll", response_model=List[ExamRead])
def getAllExam(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllExamsIsDeleteFalse(session, search, page)
    return all_exams

@router.get("/teacher/{teacherId}", response_model=List[ExamRead])
def getAllExamsOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllExamsOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_exams

@router.get("/class/{classId}", response_model=List[ExamRead])
def getAllExamsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllExamsOfClassIsDeleteFalse(classId, session, search, page)
    return all_exams