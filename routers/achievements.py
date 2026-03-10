import uuid
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from core.database import SessionDep
from models import Achievements
from repository.achievements import getAllAchievementsActive, getAchievementById, achievementSave, achievementUpdate, \
    achievementToggleActive, achievementSoftDelete
from schemas import SaveResponse, PaginatedAchievementsResponse, \
    AchievementDetail
from deps import AdminUser

router = APIRouter(
    prefix="/achievement",
)


@router.get("/getAll", response_model=PaginatedAchievementsResponse)
def getAllAchievements(session: SessionDep, search: str = None, page: int = 1):
    achievements = getAllAchievementsActive(session=session, search=search, page=page)
    return achievements


@router.get("/get/{achievementId}", response_model=AchievementDetail)
def getById(current_user: AdminUser, session: SessionDep, achievementId: uuid.UUID):
    achievement_detail: Optional[Achievements] = getAchievementById(session, achievementId)

    if not achievement_detail:
        raise HTTPException(
            status_code=404,
            detail="Achievement not found with provided ID."
        )

    return achievement_detail


@router.post("/save", response_model=SaveResponse)
async def saveAchievement(
        current_user: AdminUser,
        session: SessionDep,
        title: str = Form(...),
        description: str = Form(...),
        is_active: bool = Form(False),
        image: Union[UploadFile, str] = File()
):
    processed_image: Optional[UploadFile] = None
    if image is not None and not isinstance(image, str):
        if hasattr(image, 'filename') and hasattr(image, 'file') and image.filename:
            processed_image = image

    if not processed_image:
        raise HTTPException(
            status_code=400,
            detail="Achievement image is required."
        )

    response = await achievementSave(title, description, is_active, processed_image, session)
    return response


@router.put("/update", response_model=SaveResponse)
async def updateAchievement(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        is_active: bool = Form(False),
        image: Union[UploadFile, str, None] = File(None)
):
    try:
        achievementId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid achievement UUID format: {str(e)}"
        )

    processed_image: Optional[UploadFile] = None
    if image is not None and not isinstance(image, str):
        if hasattr(image, 'filename') and hasattr(image, 'file') and image.filename:
            processed_image = image

    response = await achievementUpdate(achievementId, title, description, is_active, processed_image, session)
    return response


@router.patch("/toggle-active", response_model=SaveResponse)
def toggleAchievementActive(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = achievementToggleActive(id, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def deleteAchievement(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = achievementSoftDelete(id, session)
    return result
