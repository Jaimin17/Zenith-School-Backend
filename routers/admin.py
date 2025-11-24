from fastapi import APIRouter
from deps import AdminUser
from core.database import SessionDep
from repository.admin import countAdmin

router = APIRouter(
    prefix="/admin",
)

@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countAdmin(session)