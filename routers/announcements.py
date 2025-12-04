import uuid
from datetime import date
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, AdminUser
from repository.announcements import getAllAnnouncementsIsDeleteFalse, getAllAnnouncementsByTeacherAndIsDeleteFalse, \
    getAllAnnouncementsByStudentAndIsDeleteFalse, getAllAnnouncementsByParentAndIsDeleteFalse, announcementSave, \
    announcementUpdate, AnnouncementSoftDelete
from schemas import AnnouncementRead, SaveResponse, AnnouncementSave, AnnouncementUpdate

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


@router.post("/save", response_model=SaveResponse)
def saveAnnouncement(announcement: AnnouncementSave, current_user: AdminUser, session: SessionDep):
    if not announcement.title or len(announcement.title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if not announcement.description or len(announcement.description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    if announcement.announcement_date and announcement.announcement_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Announcement date cannot be in the past."
        )

    response = announcementSave(announcement, session)
    return response


@router.put("/update", response_model=SaveResponse)
def updateAnnouncement(current_user: AdminUser, announcement: AnnouncementUpdate, session: SessionDep):
    if not announcement.id:
        raise HTTPException(
            status_code=400,
            detail="announcement ID is required for updating."
        )

    if not announcement.title or len(announcement.title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if not announcement.description or len(announcement.description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    if announcement.announcement_date and announcement.announcement_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Announcement date cannot be in the past."
        )

    response = announcementUpdate(announcement, session)
    return response

@router.delete("/delete", response_model=SaveResponse)
def softDeleteAnnouncement(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Announcement ID is required for deleting."
        )

    result = AnnouncementSoftDelete(id, session)
    return result
