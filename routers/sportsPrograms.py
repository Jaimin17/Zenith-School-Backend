import uuid
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from core.database import SessionDep
from models import SportsPrograms
from repository.sportsPrograms import getAllSportsProgramsActive, getSportsProgramById, sportsProgramSave, \
    sportsProgramUpdate, sportsProgramToggleActive, sportsProgramSoftDelete
from schemas import SaveResponse, PaginatedSportsProgramsResponse, \
    SportsProgramDetail
from deps import AdminUser

router = APIRouter(
    prefix="/sportProgram",
)


@router.get("/getAll", response_model=PaginatedSportsProgramsResponse)
def getAllSportsPrograms(session: SessionDep, search: str = None, page: int = 1):
    sportsPrograms = getAllSportsProgramsActive(session=session, search=search, page=page)
    return sportsPrograms


@router.get("/get/{sportId}", response_model=SportsProgramDetail)
def getById(current_user: AdminUser, session: SessionDep, sportId: uuid.UUID):
    sport_detail: Optional[SportsPrograms] = getSportsProgramById(session, sportId)

    if not sport_detail:
        raise HTTPException(
            status_code=404,
            detail="Sports program not found with provided ID."
        )

    return sport_detail


@router.post("/save", response_model=SaveResponse)
async def saveSportsProgram(
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
            detail="Banner image is required."
        )

    response = await sportsProgramSave(title, description, is_active, processed_image, session)
    return response


@router.put("/update", response_model=SaveResponse)
async def updateSportsProgram(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        is_active: bool = Form(False),
        image: Union[UploadFile, str, None] = File(None)
):
    try:
        sportsId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Sports Program UUID format: {str(e)}"
        )

    processed_image: Optional[UploadFile] = None
    if image is not None and not isinstance(image, str):
        if hasattr(image, 'filename') and hasattr(image, 'file') and image.filename:
            processed_image = image

    response = await sportsProgramUpdate(sportsId, title, description, is_active, processed_image, session)
    return response


@router.patch("/toggle-active", response_model=SaveResponse)
def toggleSportsProgramActive(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = sportsProgramToggleActive(id, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def deleteSportsProgram(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = sportsProgramSoftDelete(id, session)
    return result
