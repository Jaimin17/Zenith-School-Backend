import uuid
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from core.database import SessionDep
from models import Banner
from repository.banner import getAllBannersActive, getBannerById, bannerSave, bannerUpdate, bannerSoftDelete, \
    bannerToggleActive
from schemas import PaginatedBannerResponse, BannerDetail, SaveResponse
from deps import AdminUser

router = APIRouter(
    prefix="/banner",
)


@router.get("/getAll", response_model=PaginatedBannerResponse)
def getAllBanners(session: SessionDep, search: str = None, page: int = 1):
    banners = getAllBannersActive(session=session, search=search, page=page)
    return banners


@router.get("/get/{bannerId}", response_model=BannerDetail)
def getById(current_user: AdminUser, session: SessionDep, bannerId: uuid.UUID):
    banner_detail: Optional[Banner] = getBannerById(session, bannerId)

    if not banner_detail:
        raise HTTPException(
            status_code=404,
            detail="Banner not found with provided ID."
        )

    return banner_detail


@router.post("/save", response_model=SaveResponse)
async def saveBanner(
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

    response = await bannerSave(title, description, is_active, processed_image, session)
    return response


@router.put("/update", response_model=SaveResponse)
async def updateBanner(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        is_active: bool = Form(False),
        image: Union[UploadFile, str, None] = File(None)
):
    try:
        bannerId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid banner UUID format: {str(e)}"
        )

    processed_image: Optional[UploadFile] = None
    if image is not None and not isinstance(image, str):
        if hasattr(image, 'filename') and hasattr(image, 'file') and image.filename:
            processed_image = image

    response = await bannerUpdate(bannerId, title, description, is_active, processed_image, session)
    return response


@router.patch("/toggle-active", response_model=SaveResponse)
def toggleBannerActive(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = bannerToggleActive(id, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def deleteBanner(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = bannerSoftDelete(id, session)
    return result