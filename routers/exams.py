import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser, AllUser
from repository.exams import getAllExamsIsDeleteFalse, getAllExamsOfTeacherIsDeleteFalse, \
    getAllExamsOfClassIsDeleteFalse, getAllExamsOfParentIsDeleteFalse
from schemas import ExamRead

router = APIRouter(
    prefix="/exam",
)

@router.get("/getAll", response_model=List[ExamRead])
def getAllExam(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_exams = getAllExamsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_exams = getAllExamsOfTeacherIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_exams = getAllExamsOfClassIsDeleteFalse(user.class_id, session, search, page)
    else:
        all_exams = getAllExamsOfParentIsDeleteFalse(user.id, session, search, page)
    return all_exams

@router.get("/teacher/{teacherId}", response_model=List[ExamRead])
def getAllExamsOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllExamsOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_exams

@router.get("/class/{classId}", response_model=List[ExamRead])
def getAllExamsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllExamsOfClassIsDeleteFalse(classId, session, search, page)
    return all_exams