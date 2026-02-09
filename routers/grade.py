from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import AllUser
from repository.grade import getAllGradesIsDeleteFalse
from schemas import GradeBase

router = APIRouter(
    prefix="/grade",
)

@router.get("/getAll", response_model=List[GradeBase])
def getAllGrade(current_user: AllUser, session: SessionDep):
    all_grade = getAllGradesIsDeleteFalse(session)
    return all_grade