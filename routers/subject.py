from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.subject import getAllSubjectsIsDeleteFalse
from schemas import SubjectRead

router = APIRouter(
    prefix="/subject",
)

@router.get("/getAll", response_model=List[SubjectRead])
def getAllSubject(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_subjects = getAllSubjectsIsDeleteFalse(session, search, page)
    return all_subjects