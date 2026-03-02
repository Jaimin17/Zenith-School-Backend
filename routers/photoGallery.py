import uuid
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from core.database import SessionDep
from deps import AdminUser
from models import PhotoGallery
from repository.photoGallery import getAllPhotosActive, getPhotoById, photoSave, photoUpdate, photoToggleActive, \
    photoSoftDelete
from schemas import PaginatedPhotoGalleryResponse, PhotoGalleryDetail, SaveResponse

router = APIRouter(
    prefix="/photoGallery",
)


@router.get("/getAll", response_model=PaginatedPhotoGalleryResponse)
def getAllPhotos(session: SessionDep, search: str = None, page: int = 1):
    photos = getAllPhotosActive(session=session, search=search, page=page)
    return photos


@router.get("/get/{photoId}", response_model=PhotoGalleryDetail)
def getById(current_user: AdminUser, session: SessionDep, photoId: uuid.UUID):
    photo_detail: Optional[PhotoGallery] = getPhotoById(session, photoId)

    if not photo_detail:
        raise HTTPException(
            status_code=404,
            detail="Photo not found with provided ID."
        )

    return photo_detail


@router.post("/save", response_model=SaveResponse)
async def savePhoto(
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
            detail="Image is required."
        )

    response = await photoSave(title, description, is_active, processed_image, session)
    return response


@router.put("/update", response_model=SaveResponse)
async def updatePhoto(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        is_active: bool = Form(False),
        image: Union[UploadFile, str, None] = File(None)
):
    try:
        photoId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid photo UUID format: {str(e)}"
        )

    processed_image: Optional[UploadFile] = None
    if image is not None and not isinstance(image, str):
        if hasattr(image, 'filename') and hasattr(image, 'file') and image.filename:
            processed_image = image

    response = await photoUpdate(photoId, title, description, is_active, processed_image, session)
    return response


@router.patch("/toggle-active", response_model=SaveResponse)
def togglePhotoActive(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = photoToggleActive(id, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def deletePhoto(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = photoSoftDelete(id, session)
    return result
