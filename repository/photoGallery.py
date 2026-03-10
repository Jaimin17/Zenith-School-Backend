import uuid
from typing import Optional

from fastapi import UploadFile, HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.FileStorage import process_and_save_image, cleanup_image
from core.config import settings
from models import PhotoGallery
from schemas import PaginatedPhotoGalleryResponse

PHOTO_GALLERY_FOLDER = "photoGallery"


def addSearchOption(query: Select, search: str):
    if search is not None:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(PhotoGallery.title).like(search_pattern) |
            func.lower(PhotoGallery.description).like(search_pattern)
        )

    return query


def getAllPhotosActive(session: Session, search: str, is_sport: bool, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Base query for counting
    count_query = (
        select(func.count(PhotoGallery.id.distinct()))
        .where(
            PhotoGallery.is_delete == False,
        )
    )

    if is_sport is not None:
        count_query = count_query.where(PhotoGallery.is_sport == is_sport)

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Main query for data
    query = (
        select(PhotoGallery)
        .where(
            PhotoGallery.is_delete == False
        )
    )

    if is_sport is not None:
        query = query.where(PhotoGallery.is_sport == is_sport)
    query = query.order_by(PhotoGallery.created_at.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    photos = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedPhotoGalleryResponse(
        data=photos,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getPhotoById(session: Session, photoId: uuid.UUID):
    query = (
        select(PhotoGallery)
        .where(
            PhotoGallery.id == photoId,
            PhotoGallery.is_delete == False
        )
    )

    photo_detail = session.exec(query).first()
    return photo_detail


async def photoSave(title: str, description: str, is_active: bool, is_sport: bool, image: Optional[UploadFile],
                    session: Session):
    title = title.strip()
    description = description.strip()

    if len(title) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title is required and should be at least 3 characters long."
        )

    if len(description) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description is required and should be at least 10 characters long."
        )

    # Check for duplicate title
    duplicate_query = (
        select(PhotoGallery)
        .where(
            PhotoGallery.title.ilike(f"%{title}%"),
            PhotoGallery.is_delete == False,
            PhotoGallery.is_sport == is_sport,
        )
    )
    duplicate_photo: Optional[PhotoGallery] = session.exec(duplicate_query).first()

    if duplicate_photo:
        raise HTTPException(
            status_code=409,
            detail=f"A image with the title '{title}' already exists."
        )

    # Process image
    if not image or not image.filename:
        raise HTTPException(
            status_code=400,
            detail="Image is required."
        )

    try:
        image_filename = await process_and_save_image(image, PHOTO_GALLERY_FOLDER, title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    new_photo = PhotoGallery(
        title=title,
        description=description,
        img=image_filename,
        is_active=is_active,
        is_sport=is_sport,
        is_delete=False
    )

    session.add(new_photo)

    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        img_path = settings.UPLOAD_DIR_DP / PHOTO_GALLERY_FOLDER / image_filename
        cleanup_image(img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_photo)

    return {
        "id": str(new_photo.id),
        "message": "Gallery photo created successfully."
    }


async def photoUpdate(photoId: uuid.UUID, title: str, description: str, is_active: bool, is_sport: bool,
                      image: Optional[UploadFile], session: Session):
    photo_query = (
        select(PhotoGallery)
        .where(
            PhotoGallery.id == photoId,
            PhotoGallery.is_delete == False,
            PhotoGallery.is_sport == is_sport,
        )
    )

    current_photo: Optional[PhotoGallery] = session.exec(photo_query).first()

    if not current_photo:
        raise HTTPException(
            status_code=404,
            detail="Photo not found with provided ID."
        )

    title = title.strip()
    description = description.strip()

    if len(title) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if len(description) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    # Check for duplicate title (excluding current photo)
    duplicate_query = (
        select(PhotoGallery)
        .where(
            PhotoGallery.title.ilike(f"%{title}%"),
            PhotoGallery.id != current_photo.id,
            PhotoGallery.is_delete == False,
            PhotoGallery.is_sport == is_sport,
        )
    )
    duplicate_photo: Optional[PhotoGallery] = session.exec(duplicate_query).first()

    if duplicate_photo:
        raise HTTPException(
            status_code=409,
            detail=f"A photo with a similar title already exists."
        )

    old_image_filename = current_photo.img

    # Process new image if provided
    if image is not None:
        try:
            image_filename = await process_and_save_image(image, PHOTO_GALLERY_FOLDER, title)
            current_photo.img = image_filename
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    current_photo.title = title
    current_photo.description = description
    current_photo.is_active = is_active
    current_photo.is_sport = is_sport

    session.add(current_photo)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Clean up new image if it was uploaded
        if image is not None and current_photo.img != old_image_filename:
            new_img_path = settings.UPLOAD_DIR_DP / PHOTO_GALLERY_FOLDER / current_photo.img
            cleanup_image(new_img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_photo)

    return {
        "id": str(current_photo.id),
        "message": "Photo updated successfully."
    }


def photoSoftDelete(photoId: uuid.UUID, session: Session):
    photo_query = (
        select(PhotoGallery)
        .where(
            PhotoGallery.id == photoId,
            PhotoGallery.is_delete == False
        )
    )

    current_photo: Optional[PhotoGallery] = session.exec(photo_query).first()

    if not current_photo:
        raise HTTPException(
            status_code=404,
            detail="Photo not found or already deleted."
        )

    current_photo.is_delete = True

    try:
        session.add(current_photo)
        session.commit()
        session.refresh(current_photo)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while deleting photo."
        )

    return {
        "id": str(current_photo.id),
        "message": "Photo deleted successfully."
    }


def photoToggleActive(photoId: uuid.UUID, session: Session):
    photo_query = (
        select(PhotoGallery)
        .where(
            PhotoGallery.id == photoId,
            PhotoGallery.is_delete == False
        )
    )

    current_photo: Optional[PhotoGallery] = session.exec(photo_query).first()

    if not current_photo:
        raise HTTPException(
            status_code=404,
            detail="Photo not found or already deleted."
        )

    current_photo.is_active = not current_photo.is_active

    try:
        session.add(current_photo)
        session.commit()
        session.refresh(current_photo)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while updating photo status."
        )

    status_text = "activated" if current_photo.is_active else "deactivated"
    return {
        "id": str(current_photo.id),
        "message": f"Photo {status_text} successfully."
    }
