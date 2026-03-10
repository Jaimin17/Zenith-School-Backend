import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import select, Session

from core.FileStorage import process_and_save_image, cleanup_image
from core.config import settings
from models import Banner, Achievements
from schemas import PaginatedBannerResponse, PaginatedAchievementsResponse

ACHIEVEMENTS_IMAGE_FOLDER = "achievements"


def addSearchOption(query: Select, search: str):
    if search is not None:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Achievements.title).like(search_pattern) |
            func.lower(Achievements.description).like(search_pattern)
        )

    return query


def getAllAchievementsActive(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Base query for counting
    count_query = (
        select(func.count(Achievements.id.distinct()))
        .where(Achievements.is_delete == False)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Main query for data
    query = (
        select(Achievements)
        .where(Achievements.is_delete == False)
    )
    query = query.order_by(Achievements.created_at.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    achievements = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedAchievementsResponse(
        data=achievements,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAchievementById(session: Session, achievementId: uuid.UUID):
    query = (
        select(Achievements)
        .where(
            Achievements.id == achievementId,
            Achievements.is_delete == False
        )
    )

    achievement_detail = session.exec(query).first()
    return achievement_detail


async def achievementSave(title: str, description: str, is_active: bool, image: Optional[UploadFile], session: Session):
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
        select(Achievements)
        .where(
            Achievements.title.ilike(f"%{title}%"),
            Achievements.is_delete == False
        )
    )
    duplicate_achievement: Optional[Achievements] = session.exec(duplicate_query).first()

    if duplicate_achievement:
        raise HTTPException(
            status_code=409,
            detail=f"A achievement with the title '{title}' already exists."
        )

    # Process image
    if not image or not image.filename:
        raise HTTPException(
            status_code=400,
            detail="Achievement image is required."
        )

    try:
        image_filename = await process_and_save_image(image, ACHIEVEMENTS_IMAGE_FOLDER, title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    new_achievement = Achievements(
        title=title,
        description=description,
        img=image_filename,
        is_active=is_active,
        is_delete=False
    )

    session.add(new_achievement)

    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        img_path = settings.UPLOAD_DIR_DP / ACHIEVEMENTS_IMAGE_FOLDER / image_filename
        cleanup_image(img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_achievement)

    return {
        "id": str(new_achievement.id),
        "message": "Achievement created successfully."
    }


async def achievementUpdate(achievementId: uuid.UUID, title: str, description: str, is_active: bool,
                            image: Optional[UploadFile], session: Session):
    achievement_query = (
        select(Achievements)
        .where(Achievements.id == achievementId, Achievements.is_delete == False)
    )

    current_achievement: Optional[Achievements] = session.exec(achievement_query).first()

    if not current_achievement:
        raise HTTPException(
            status_code=404,
            detail="Achievement not found with provided ID."
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

    # Check for duplicate title (excluding current achievement)
    duplicate_query = (
        select(Achievements)
        .where(
            Achievements.title.ilike(f"%{title}%"),
            Achievements.id != current_achievement.id,
            Achievements.is_delete == False
        )
    )
    duplicate_achievement: Optional[Achievements] = session.exec(duplicate_query).first()

    if duplicate_achievement:
        raise HTTPException(
            status_code=409,
            detail=f"A achievement with a similar title already exists."
        )

    old_image_filename = current_achievement.img

    # Process new image if provided
    if image is not None:
        try:
            image_filename = await process_and_save_image(image, ACHIEVEMENTS_IMAGE_FOLDER, title)
            current_achievement.img = image_filename
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    current_achievement.title = title
    current_achievement.description = description
    current_achievement.is_active = is_active

    session.add(current_achievement)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Clean up new image if it was uploaded
        if image is not None and current_achievement.img != old_image_filename:
            new_img_path = settings.UPLOAD_DIR_DP / ACHIEVEMENTS_IMAGE_FOLDER / current_achievement.img
            cleanup_image(new_img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_achievement)

    return {
        "id": str(current_achievement.id),
        "message": "Achievement updated successfully."
    }


def achievementSoftDelete(achievementId: uuid.UUID, session: Session):
    achievement_query = (
        select(Achievements)
        .where(
            Achievements.id == achievementId,
            Achievements.is_delete == False
        )
    )

    current_achievement: Optional[Achievements] = session.exec(achievement_query).first()

    if not current_achievement:
        raise HTTPException(
            status_code=404,
            detail="Achievement not found or already deleted."
        )

    current_achievement.is_delete = True

    try:
        session.add(current_achievement)
        session.commit()
        session.refresh(current_achievement)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while deleting achievement."
        )

    return {
        "id": str(current_achievement.id),
        "message": "Achievement deleted successfully."
    }


def achievementToggleActive(achievementId: uuid.UUID, session: Session):
    achievement_query = (
        select(Achievements)
        .where(
            Achievements.id == achievementId,
            Achievements.is_delete == False
        )
    )

    current_achievement: Optional[Achievements] = session.exec(achievement_query).first()

    if not current_achievement:
        raise HTTPException(
            status_code=404,
            detail="Achievement not found or already deleted."
        )

    current_achievement.is_active = not current_achievement.is_active

    try:
        session.add(current_achievement)
        session.commit()
        session.refresh(current_achievement)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while updating achievement status."
        )

    status_text = "activated" if current_achievement.is_active else "deactivated"
    return {
        "id": str(current_achievement.id),
        "message": f"Banner {status_text} successfully."
    }
