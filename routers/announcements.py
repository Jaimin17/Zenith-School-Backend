from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser
from repository.announcements import getAllAnnouncementsIsDeleteFalse
from schemas import AnnouncementRead

router = APIRouter(
    prefix="/announcements",
)

@router.get("/getAll", response_model=List[AnnouncementRead])
def getAllAnnouncements(current_user: CurrentUser, session: SessionDep, search: str = None, page: int = 1):
    announcements = getAllAnnouncementsIsDeleteFalse(session, search, page)
    return announcements