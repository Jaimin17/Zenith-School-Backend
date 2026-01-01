import uuid
from datetime import date
from typing import List, Union, Optional
from core.database import SessionDep
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from deps import CurrentUser, AllUser, AdminUser, TeacherOrAdminUser
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
async def saveAnnouncement(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        title: str = Form(...),
        description: str = Form(...),
        announcement_date: date = Form(...),
        class_id: Optional[str] = Form(None),
        pdf: Union[UploadFile, str, None] = File(None)
):
    user, role = current_user

    if not title or len(title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title is required and should be at least 3 characters long."
        )

    if not description or len(description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description is required and should be at least 10 characters long."
        )

    if announcement_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Announcement date cannot be in the past."
        )

    if role == "Admin":
        class_uuid: Optional[uuid.UUID] = None
        if class_id and class_id.strip():
            try:
                class_uuid = uuid.UUID(class_id.strip())
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid Class UUID format: {str(e)}"
                )
    else:
        if not class_id or not class_id.strip():
            raise HTTPException(
                status_code=404,
                detail="Class UUID is required."
            )

        try:
            class_uuid = uuid.UUID(class_id.strip())
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Class UUID format: {str(e)}"
            )

    processed_pdf: Optional[UploadFile] = None
    if pdf is not None and not isinstance(pdf, str):
        if hasattr(pdf, 'filename') and hasattr(pdf, 'file') and pdf.filename:
            processed_pdf = pdf

    announcement = AnnouncementSave(
        title=title.strip(),
        description=description.strip(),
        announcement_date=announcement_date,
        class_id=class_uuid,
    )

    response = await announcementSave(announcement, processed_pdf, user.id, role, session)
    return response


@router.put("/update", response_model=SaveResponse)
async def updateAnnouncement(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        announcement_date: date = Form(...),
        class_id: Optional[str] = Form(None),
        pdf: Union[UploadFile, str, None] = File(None)
    ):
    user, role = current_user

    try:
        announcementId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid announcement UUID format: {str(e)}"
        )

    if not title or len(title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title is required and should be at least 3 characters long."
        )

    if not description or len(description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description is required and should be at least 10 characters long."
        )

    if announcement_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Announcement date cannot be in the past."
        )

    if role == "Admin":
        class_uuid: Optional[uuid.UUID] = None
        if class_id and class_id.strip():
            try:
                class_uuid = uuid.UUID(class_id.strip())
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid Class UUID format: {str(e)}"
                )
    else:
        if not class_id or not class_id.strip():
            raise HTTPException(
                status_code=404,
                detail="Class UUID is required."
            )

        try:
            class_uuid = uuid.UUID(class_id.strip())
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Class UUID format: {str(e)}"
            )

    processed_pdf: Optional[UploadFile] = None
    if pdf is not None and not isinstance(pdf, str):
        if hasattr(pdf, 'filename') and hasattr(pdf, 'file') and pdf.filename:
            processed_pdf = pdf

    announcement = AnnouncementUpdate(
        id=announcementId,
        title=title.strip(),
        description=description.strip(),
        announcement_date=announcement_date,
        class_id=class_uuid,
    )

    response = await announcementUpdate(announcement, processed_pdf, user.id, role, session)
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
