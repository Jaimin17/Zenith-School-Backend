from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser, AdminUser, TeacherOrAdminUser
from repository.parent import getAllParentIsDeleteFalse, countParent
from schemas import ParentRead

router = APIRouter(
    prefix="/parent",
)

@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countParent(session)


@router.get("/getAll", response_model=List[ParentRead])
def getAllParent(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    all_parents = getAllParentIsDeleteFalse(session, search, page)
    return all_parents