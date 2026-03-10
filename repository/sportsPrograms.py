import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import select, Session

from core.FileStorage import process_and_save_image, cleanup_image
from core.config import settings
from models import Banner, SportsPrograms
from schemas import PaginatedBannerResponse, PaginatedSportsProgramsResponse

SPORTS_PROGRAM_IMAGE_FOLDER = "sportProgram"


def addSearchOption(query: Select, search: str):
    if search is not None:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(SportsPrograms.title).like(search_pattern) |
            func.lower(SportsPrograms.description).like(search_pattern)
        )

    return query


def getAllSportsProgramsActive(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Base query for counting
    count_query = (
        select(func.count(SportsPrograms.id.distinct()))
        .where(SportsPrograms.is_delete == False)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Main query for data
    query = (
        select(SportsPrograms)
        .where(SportsPrograms.is_delete == False)
    )
    query = query.order_by(SportsPrograms.created_at.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    sportsPrograms = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedSportsProgramsResponse(
        data=sportsPrograms,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getSportsProgramById(session: Session, sportId: uuid.UUID):
    query = (
        select(SportsPrograms)
        .where(
            SportsPrograms.id == sportId,
            SportsPrograms.is_delete == False
        )
    )

    sport_program_detail = session.exec(query).first()
    return sport_program_detail


async def sportsProgramSave(title: str, description: str, is_active: bool, image: Optional[UploadFile],
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
        select(SportsPrograms)
        .where(
            SportsPrograms.title.ilike(f"%{title}%"),
            SportsPrograms.is_delete == False
        )
    )
    duplicate_sports_program: Optional[SportsPrograms] = session.exec(duplicate_query).first()

    if duplicate_sports_program:
        raise HTTPException(
            status_code=409,
            detail=f"A sports program with the title '{title}' already exists."
        )

    # Process image
    if not image or not image.filename:
        raise HTTPException(
            status_code=400,
            detail="Sports Program image is required."
        )

    try:
        image_filename = await process_and_save_image(image, SPORTS_PROGRAM_IMAGE_FOLDER, title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    new_sports_program = SportsPrograms(
        title=title,
        description=description,
        img=image_filename,
        is_active=is_active,
        is_delete=False
    )

    session.add(new_sports_program)

    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        img_path = settings.UPLOAD_DIR_DP / SPORTS_PROGRAM_IMAGE_FOLDER / image_filename
        cleanup_image(img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_sports_program)

    return {
        "id": str(new_sports_program.id),
        "message": "Sports Program created successfully."
    }


async def sportsProgramUpdate(sportsId: uuid.UUID, title: str, description: str, is_active: bool,
                              image: Optional[UploadFile], session: Session):
    sports_program_query = (
        select(SportsPrograms)
        .where(SportsPrograms.id == sportsId, SportsPrograms.is_delete == False)
    )

    current_sport_program: Optional[SportsPrograms] = session.exec(sports_program_query).first()

    if not current_sport_program:
        raise HTTPException(
            status_code=404,
            detail="Sports Program not found with provided ID."
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
        select(SportsPrograms)
        .where(
            SportsPrograms.title.ilike(f"%{title}%"),
            SportsPrograms.id != current_sport_program.id,
            SportsPrograms.is_delete == False
        )
    )
    duplicate_sport_program: Optional[SportsPrograms] = session.exec(duplicate_query).first()

    if duplicate_sport_program:
        raise HTTPException(
            status_code=409,
            detail=f"A sports program with a similar title already exists."
        )

    old_image_filename = current_sport_program.img

    # Process new image if provided
    if image is not None:
        try:
            image_filename = await process_and_save_image(image, SPORTS_PROGRAM_IMAGE_FOLDER, title)
            current_sport_program.img = image_filename
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    current_sport_program.title = title
    current_sport_program.description = description
    current_sport_program.is_active = is_active

    session.add(current_sport_program)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Clean up new image if it was uploaded
        if image is not None and current_sport_program.img != old_image_filename:
            new_img_path = settings.UPLOAD_DIR_DP / SPORTS_PROGRAM_IMAGE_FOLDER / current_sport_program.img
            cleanup_image(new_img_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_sport_program)

    return {
        "id": str(current_sport_program.id),
        "message": "Sports Program updated successfully."
    }


def sportsProgramSoftDelete(sportsId: uuid.UUID, session: Session):
    sport_program_query = (
        select(SportsPrograms)
        .where(
            SportsPrograms.id == sportsId,
            SportsPrograms.is_delete == False
        )
    )

    current_sport_program: Optional[SportsPrograms] = session.exec(sport_program_query).first()

    if not current_sport_program:
        raise HTTPException(
            status_code=404,
            detail="Sports Program not found or already deleted."
        )

    current_sport_program.is_delete = True

    try:
        session.add(current_sport_program)
        session.commit()
        session.refresh(current_sport_program)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while deleting sports program."
        )

    return {
        "id": str(current_sport_program.id),
        "message": "Sport program deleted successfully."
    }


def sportsProgramToggleActive(sportsId: uuid.UUID, session: Session):
    sport_program_query = (
        select(SportsPrograms)
        .where(
            SportsPrograms.id == sportsId,
            SportsPrograms.is_delete == False
        )
    )

    current_sport_program: Optional[SportsPrograms] = session.exec(sport_program_query).first()

    if not current_sport_program:
        raise HTTPException(
            status_code=404,
            detail="Sports Program not found or already deleted."
        )

    current_sport_program.is_active = not current_sport_program.is_active

    try:
        session.add(current_sport_program)
        session.commit()
        session.refresh(current_sport_program)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while updating sport program status."
        )

    status_text = "activated" if current_sport_program.is_active else "deactivated"
    return {
        "id": str(current_sport_program.id),
        "message": f"Sports Program {status_text} successfully."
    }
