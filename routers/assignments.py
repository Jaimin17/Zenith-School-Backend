import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.assignments import getAllAssignmentsIsDeleteFalse, getAllAssignmentsOfTeacherIsDeleteFalse, \
    getAllAssignmentsOfClassIsDeleteFalse
from schemas import AssignmentRead

router = APIRouter(
    prefix="/assignments",
)

@router.get("/getAll", response_model=List[AssignmentRead])
def getAllExam(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllAssignmentsIsDeleteFalse(session, search, page)
    return all_exams

@router.get("/teacher/{teacherId}", response_model=List[AssignmentRead])
def getAllExamsOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllAssignmentsOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_exams

@router.get("/class/{classId}", response_model=List[AssignmentRead])
def getAllExamsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_exams = getAllAssignmentsOfClassIsDeleteFalse(classId, session, search, page)
    return all_exams