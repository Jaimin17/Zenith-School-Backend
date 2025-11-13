from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.parent import getAllParentIsDeleteFalse
from schemas import ParentRead

router = APIRouter(
    prefix="/parent",
)

@router.get("/getAll", response_model=List[ParentRead])
def getAllParent(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_parents = getAllParentIsDeleteFalse(session, search, page)
    return all_parents