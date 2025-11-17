from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.events import getAllEventsIsDeleteFalse
from schemas import EventRead

router = APIRouter(
    prefix="/events",
)

@router.get("/getAll", response_model=List[EventRead])
def getAllEvents(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    all_events = getAllEventsIsDeleteFalse(session, search, page)
    return all_events