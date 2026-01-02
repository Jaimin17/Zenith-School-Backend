import uuid
from datetime import date
from typing import List, Union, Optional
from core.database import SessionDep
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from deps import CurrentUser, AllUser, AdminUser, TeacherOrAdminUser
from models import Announcement
from repository.announcements import getAllAnnouncementsIsDeleteFalse, getAllAnnouncementsByTeacherAndIsDeleteFalse, \
    getAllAnnouncementsByStudentAndIsDeleteFalse, getAllAnnouncementsByParentAndIsDeleteFalse, announcementSave, \
    announcementUpdate, AnnouncementSoftDelete, getAnnouncementById
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


@router.get("/getById/{announcementId}", response_model=AnnouncementRead)
def getById(current_user: AllUser, session: SessionDep, announcementId: uuid.UUID):
    user, role = current_user

    announcement_detail: Optional[Announcement] = getAnnouncementById(session, announcementId)

    if not announcement_detail:
        raise HTTPException(
            status_code=404,
            detail="Announcement not found with provided ID."
        )

    if announcement_detail.class_id is None:
        return announcement_detail

    if role.lower() == "admin":
        return announcement_detail

    elif role.lower() == "teacher":
        if announcement_detail.related_class.supervisor_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this announcement."
            )
        return announcement_detail

    elif role.lower() == "student":
        if not announcement_detail.related_class:
            raise HTTPException(
                status_code=500,
                detail="Announcement class data is missing."
            )

        class_students = [s.id for s in announcement_detail.related_class.students if not s.is_delete]
        if user.id not in class_students:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this announcement."
            )
        return announcement_detail

    elif role.lower() == "parent":
        if not user.students:
            raise HTTPException(
                status_code=403,
                detail="No students associated with your account."
            )

        if not announcement_detail.related_class:
            raise HTTPException(
                status_code=500,
                detail="Announcement class data is missing."
            )

        class_student_ids = [s.id for s in announcement_detail.related_class.students if not s.is_delete]
        parent_student_ids = [s.id for s in user.students if not s.is_delete]

        # Check if any of parent's students are in the class
        has_access = any(student_id in class_student_ids for student_id in parent_student_ids)

        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="None of your children have access to this announcement."
            )

        return announcement_detail

    else:
        raise HTTPException(
            status_code=403,
            detail="Invalid user role."
        )


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

    if role == "admin":
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
