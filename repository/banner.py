import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import select, Session

from core.FileStorage import process_and_save_image, cleanup_image
from core.config import settings
from models import Banner
from schemas import PaginatedBannerResponse

BANNER_IMAGE_FOLDER = "banners"


def addSearchOption(query: Select, search: str):
    if search is not None:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Banner.title).like(search_pattern) |
            func.lower(Banner.description).like(search_pattern)
        )

    return query


def getAllBannersActive(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Base query for counting
    count_query = (
        select(func.count(Banner.id.distinct()))
        .where(Banner.is_delete == False)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Main query for data
    query = (
        select(Banner)
        .where(Banner.is_delete == False)
    )
    query = query.order_by(Banner.created_at.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    banners = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedBannerResponse(
        data=banners,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getBannerById(session: Session, bannerId: uuid.UUID):
    query = (
        select(Banner)
        .where(
            Banner.id == bannerId,
            Banner.is_delete == False
        )
    )

    banner_detail = session.exec(query).first()
    return banner_detail


async def bannerSave(title: str, description: str, is_active: bool, image: Optional[UploadFile], session: Session):
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
        select(Banner)
        .where(
            Banner.title.ilike(f"%{title}%"),
            Banner.is_delete == False
        )
    )
    duplicate_banner: Optional[Banner] = session.exec(duplicate_query).first()

    if duplicate_banner:
        raise HTTPException(
            status_code=409,
            detail=f"A banner with the title '{title}' already exists."
        )

    # Process image
    if not image or not image.filename:
        raise HTTPException(
            status_code=400,
            detail="Banner image is required."
        )

    try:
        image_filename = await process_and_save_image(image, BANNER_IMAGE_FOLDER, title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    new_banner = Banner(
        title=title,
        description=description,
        img=image_filename,
        is_active=is_active,
        is_delete=False
    )

    session.add(new_banner)

    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        img_path = settings.UPLOAD_DIR_DP / BANNER_IMAGE_FOLDER / image_filename
        cleanup_image(img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_banner)

    return {
        "id": str(new_banner.id),
        "message": "Banner created successfully."
    }


async def bannerUpdate(bannerId: uuid.UUID, title: str, description: str, is_active: bool,
                       image: Optional[UploadFile], session: Session):
    banner_query = (
        select(Banner)
        .where(Banner.id == bannerId, Banner.is_delete == False)
    )

    current_banner: Optional[Banner] = session.exec(banner_query).first()

    if not current_banner:
        raise HTTPException(
            status_code=404,
            detail="Banner not found with provided ID."
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

    # Check for duplicate title (excluding current banner)
    duplicate_query = (
        select(Banner)
        .where(
            Banner.title.ilike(f"%{title}%"),
            Banner.id != current_banner.id,
            Banner.is_delete == False
        )
    )
    duplicate_banner: Optional[Banner] = session.exec(duplicate_query).first()

    if duplicate_banner:
        raise HTTPException(
            status_code=409,
            detail=f"A banner with a similar title already exists."
        )

    old_image_filename = current_banner.img

    # Process new image if provided
    if image is not None:
        try:
            image_filename = await process_and_save_image(image, BANNER_IMAGE_FOLDER, title)
            current_banner.img = image_filename
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    current_banner.title = title
    current_banner.description = description
    current_banner.is_active = is_active

    session.add(current_banner)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Clean up new image if it was uploaded
        if image is not None and current_banner.img != old_image_filename:
            new_img_path = settings.UPLOAD_DIR_DP / BANNER_IMAGE_FOLDER / current_banner.img
            cleanup_image(new_img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_banner)

    return {
        "id": str(current_banner.id),
        "message": "Banner updated successfully."
    }


def bannerSoftDelete(bannerId: uuid.UUID, session: Session):
    banner_query = (
        select(Banner)
        .where(
            Banner.id == bannerId,
            Banner.is_delete == False
        )
    )

    current_banner: Optional[Banner] = session.exec(banner_query).first()

    if not current_banner:
        raise HTTPException(
            status_code=404,
            detail="Banner not found or already deleted."
        )

    current_banner.is_delete = True

    try:
        session.add(current_banner)
        session.commit()
        session.refresh(current_banner)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while deleting banner."
        )

    return {
        "id": str(current_banner.id),
        "message": "Banner deleted successfully."
    }


def bannerToggleActive(bannerId: uuid.UUID, session: Session):
    banner_query = (
        select(Banner)
        .where(
            Banner.id == bannerId,
            Banner.is_delete == False
        )
    )

    current_banner: Optional[Banner] = session.exec(banner_query).first()

    if not current_banner:
        raise HTTPException(
            status_code=404,
            detail="Banner not found or already deleted."
        )

    current_banner.is_active = not current_banner.is_active

    try:
        session.add(current_banner)
        session.commit()
        session.refresh(current_banner)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while updating banner status."
        )

    status_text = "activated" if current_banner.is_active else "deactivated"
    return {
        "id": str(current_banner.id),
        "message": f"Banner {status_text} successfully."
    }
