from fastapi import APIRouter
from repository.user import register_user
from schemas import UserBase, RegisterUser
from core.database import SessionDep

router = APIRouter(
    prefix="/user"
)

@router.post("/register", response_model=UserBase)
def register(request: RegisterUser, session: SessionDep):
    return register_user(request, session)