import uuid
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Testimonials, User, Student
from routers import student
from schemas import PaginatedTestimonialsResponse


def addSearchOption(query: Select, search: str):
    if search is not None:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Testimonials.description).like(search_pattern)
        )

    return query


def getAllTestimonialsActive(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Testimonials.id.distinct()))
        .where(Testimonials.is_delete == False)
    )
    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    # Main query for data
    query = (
        select(Testimonials)
        .where(Testimonials.is_delete == False)
    )
    query = query.order_by(Testimonials.created_at.desc())
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    testimonials = session.exec(query).unique().all()

    # Calculate pagination metadata
    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedTestimonialsResponse(
        data=testimonials,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 0
    )


def getAllActiveTestimonialsAndIsDeleteFalse(session: Session):
    query = (
        select(Testimonials)
        .where(
            Testimonials.is_active == True,
            Testimonials.is_delete == False
        )
    )
    query = query.order_by(Testimonials.created_at.desc())
    query = query.limit(5)
    testimonials = session.exec(query).unique().all()

    return testimonials


def getTestimonialById(session: Session, testimonial_id: int, role: str, user_id: uuid.UUID):
    query = (
        select(Testimonials)
        .where(
            Testimonials.id == testimonial_id,
            Testimonials.student_id == user_id,
            Testimonials.is_delete == False
        )
    )

    testimonial_detail = session.exec(query).one()
    return testimonial_detail


def testimonialSave(rating: float, description: str, is_active: bool, session: Session, user: Student):
    # Check for duplicate title
    duplicate_query = (
        select(Testimonials)
        .where(
            Testimonials.student_id == user.id,
            Testimonials.is_delete == False
        )
    )
    duplicate_testimonial: Optional[Testimonials] = session.exec(duplicate_query).first()

    if duplicate_testimonial:
        raise HTTPException(
            status_code=409,
            detail=f"A testimonial with the student '{user.username}' already exists."
        )

    new_testimonial = Testimonials(
        rating=rating,
        description=description,
        student_id=user.id,
        is_active=is_active,
        is_delete=False
    )

    session.add(new_testimonial)

    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_testimonial)

    return {
        "id": str(new_testimonial.id),
        "message": "Testimonial created successfully."
    }


def testimonialUpdate(testimonial_id: uuid.UUID, rating: float, description: str, is_active: bool, session: Session,
                      user: Student):
    testimonial_query = (
        select(Testimonials)
        .where(
            Testimonials.id == testimonial_id,
            Testimonials.is_delete == False,
            Testimonials.student_id == user.id,
        )
    )

    current_testimonial = session.exec(testimonial_query).one()

    if not current_testimonial:
        raise HTTPException(
            status_code=404,
            detail="Testimonial not found with provided ID."
        )

    # Check for duplicate title (excluding current testimonial)
    duplicate_query = (
        select(Testimonials)
        .where(
            Testimonials.id != current_testimonial.id,
            Testimonials.student_id == user.id,
            Testimonials.is_delete == False
        )
    )
    duplicate_testimonial: Optional[Testimonials] = session.exec(duplicate_query).first()

    if duplicate_testimonial:
        raise HTTPException(
            status_code=409,
            detail=f"A testimonial with a similar title already exists."
        )

    current_testimonial.description = description
    current_testimonial.rating = rating
    current_testimonial.is_active = is_active

    session.add(current_testimonial)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_testimonial)

    return {
        "id": str(current_testimonial.id),
        "message": "Testimonial updated successfully."
    }


def testimonialToggleActive(testimonialId: uuid.UUID, session: Session):
    testimonial_query = (
        select(Testimonials)
        .where(
            Testimonials.id == testimonialId,
            Testimonials.is_delete == False,
        )
    )

    current_testimonial = session.exec(testimonial_query).one()

    if not current_testimonial:
        raise HTTPException(
            status_code=404,
            detail="Testimonial not found with provided ID."
        )

    current_testimonial.is_active = not current_testimonial.is_active

    try:
        session.add(current_testimonial)
        session.commit()
        session.refresh(current_testimonial)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while updating testimonial status."
        )

    status_text = "activated" if current_testimonial.is_active else "deactivated"
    return {
        "id": str(current_testimonial.id),
        "message": f"Testimonial {status_text} successfully."
    }


def testimonailSoftDelete(testimonial_id: uuid.UUID, session: Session):
    testimonial_query = (
        select(Testimonials)
        .where(
            Testimonials.id == testimonial_id,
            Testimonials.is_delete == False
        )
    )

    current_testimonial: Optional[Testimonials] = session.exec(testimonial_query).first()

    if not current_testimonial:
        raise HTTPException(
            status_code=404,
            detail="Testimonial not found or already deleted."
        )

    current_testimonial.is_delete = True

    try:
        session.add(current_testimonial)
        session.commit()
        session.refresh(current_testimonial)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error while deleting testimonial."
        )

    return {
        "id": str(current_testimonial.id),
        "message": "Testimonial deleted successfully."
    }
