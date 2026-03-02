import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Form
from deps import StudentOrAdminUser, StudentUser, AdminUser
from models import Testimonials
from repository.testimonials import getAllTestimonialsActive, getTestimonialById, testimonialSave, testimonialUpdate, \
    testimonialToggleActive, testimonailSoftDelete, getAllActiveTestimonialsAndIsDeleteFalse
from schemas import PaginatedTestimonialsResponse, TestimonialsDetail, SaveResponse
from core.database import SessionDep

router = APIRouter(
    prefix="/testimonials",
)


@router.get("/getAll", response_model=PaginatedTestimonialsResponse)
def getAllTestimonials(session: SessionDep, search: str = None, page: int = 1):
    testimonials = getAllTestimonialsActive(session=session, search=search, page=page)
    return testimonials


@router.get("/getAllActive", response_model=List[TestimonialsDetail])
def getAllActiveTestimonials(session: SessionDep):
    testimonials = getAllActiveTestimonialsAndIsDeleteFalse(session=session)
    return testimonials


@router.get("/get/{testimonialId}", response_model=TestimonialsDetail)
def getById(current_user: StudentOrAdminUser, session: SessionDep, testimonialId: uuid.UUID):
    user, role = current_user

    testimonial_detail: Optional[Testimonials] = getTestimonialById(session, testimonialId, role, user.id)

    if not testimonial_detail:
        raise HTTPException(
            status_code=404,
            detail="Testimonial not found with provided ID."
        )

    return testimonial_detail


@router.post("/save", response_model=SaveResponse)
def saveTestimonial(
        current_user: StudentUser,
        session: SessionDep,
        description: str = Form(...),
        rating: float = Form(...),
        is_active: bool = Form(False)
):
    user, role = current_user
    description = description.strip()

    if not description or len(description) < 4:
        raise HTTPException(
            status_code=400,
            detail="Description must be at least 4 characters long."
        )

    if not rating or rating < 0 or rating > 5:
        raise HTTPException(
            status_code=400,
            detail="Rating must be between 0 and 5."
        )

    response = testimonialSave(rating, description, is_active, session, user)
    return response


@router.put("/update", response_model=SaveResponse)
def updateTestimonial(
        current_user: StudentUser,
        session: SessionDep,
        id: str = Form(...),
        rating: float = Form(...),
        description: str = Form(...),
        is_active: bool = Form(False)
):
    user, role = current_user

    description = description.strip()

    try:
        testimonial_id = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid testimonial UUID format: {str(e)}"
        )

    if not description or len(description) < 4:
        raise HTTPException(
            status_code=400,
            detail="Description must be at least 4 characters long."
        )

    if not rating or rating < 0 or rating > 5:
        raise HTTPException(
            status_code=400,
            detail="Rating must be between 0 and 5."
        )

    response = testimonialUpdate(testimonial_id, rating, description, is_active, session, user)
    return response


@router.patch("/toggle-active", response_model=SaveResponse)
def toggleTestimonialActive(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = testimonialToggleActive(id, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def deleteTestimonail(current_user: StudentOrAdminUser, id: uuid.UUID, session: SessionDep):
    result = testimonailSoftDelete(id, session)
    return result
