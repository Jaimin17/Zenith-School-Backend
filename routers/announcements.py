from typing import List
from core.database import SessionDep
from fastapi import APIRouter
from deps import CurrentUser, AllUser
from repository.announcements import getAllAnnouncementsIsDeleteFalse, getAllAnnouncementsByTeacherAndIsDeleteFalse, \
    getAllAnnouncementsByStudentAndIsDeleteFalse, getAllAnnouncementsByParentAndIsDeleteFalse
from schemas import AnnouncementRead

router = APIRouter(
    prefix="/announcements",
)

@router.get("/getAll", response_model=List[AnnouncementRead])
def getAllAnnouncements(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        announcements = getAllAnnouncementsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        announcements = getAllAnnouncementsByTeacherAndIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        announcements = getAllAnnouncementsByStudentAndIsDeleteFalse(user.id, session, search, page)
    else:
        announcements = getAllAnnouncementsByParentAndIsDeleteFalse(user.id, session, search, page)
    return announcements