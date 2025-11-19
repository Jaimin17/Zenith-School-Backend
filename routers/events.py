from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser, AllUser
from repository.events import getAllEventsIsDeleteFalse, getAllEventsByTeacherAndIsDeleteFalse, \
    getAllEventsByStudentAndIsDeleteFalse, getAllEventsByParentAndIsDeleteFalse
from schemas import EventRead

router = APIRouter(
    prefix="/events",
)

@router.get("/getAll", response_model=List[EventRead])
def getAllEvents(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_events = getAllEventsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_events = getAllEventsByTeacherAndIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_events = getAllEventsByStudentAndIsDeleteFalse(user.id, session, search, page)
    else:
        all_events = getAllEventsByParentAndIsDeleteFalse(user.id, session, search, page)
    return all_events