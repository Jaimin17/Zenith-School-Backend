import uuid
from typing import Optional, Union

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.FileStorage import process_and_save_resume, cleanup_pdf
from core.config import settings
from models import JobApplications, JobOpenings, ApplicationStatus
from schemas import PaginatedJobApplicationResponse

VALID_STATUSES = [s.value for s in ApplicationStatus]


def _add_search_option(query: Select, search: Optional[str]):
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(JobApplications.name).like(pattern) |
            func.lower(JobApplications.email).like(pattern) |
            func.lower(JobApplications.phone).like(pattern)
        )
    return query


def getAllJobApplications(
        session: Session,
        search: Optional[str],
        page: int,
        opening_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        is_reviewed: Optional[bool] = None,
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = select(func.count(JobApplications.id.distinct())).where(JobApplications.is_delete == False)
    if opening_id:
        count_query = count_query.where(JobApplications.jobOpening_id == opening_id)
    if status:
        count_query = count_query.where(JobApplications.status == status)
    if is_reviewed is not None:
        count_query = count_query.where(JobApplications.is_reviewed == is_reviewed)
    count_query = _add_search_option(count_query, search)
    total_count = session.exec(count_query).one()

    query = select(JobApplications).where(JobApplications.is_delete == False)
    if opening_id:
        query = query.where(JobApplications.jobOpening_id == opening_id)
    if status:
        query = query.where(JobApplications.status == status)
    if is_reviewed is not None:
        query = query.where(JobApplications.is_reviewed == is_reviewed)
    query = _add_search_option(query, search)
    query = query.order_by(JobApplications.created_at.desc()).offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    applications = session.exec(query).all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedJobApplicationResponse(
        data=list(applications),
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def getJobApplicationById(session: Session, application_id: uuid.UUID):
    return session.exec(
        select(JobApplications).where(
            JobApplications.id == application_id,
            JobApplications.is_delete == False,
        )
    ).first()


async def jobApplicationSave(
        name: str,
        email: str,
        phone: str,
        location: str,
        jobOpening_id: str,
        about_applicant: str,
        resume: UploadFile,
        session: Session,
        portfolio_link: Optional[str] = None,
):
    name = name.strip()
    email = email.strip()
    phone = phone.strip()
    location = location.strip()
    about_applicant = about_applicant.strip()

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters long.")
    if len(email) < 5 or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if len(phone) < 7:
        raise HTTPException(status_code=400, detail="A valid phone number is required.")
    if len(location) < 2:
        raise HTTPException(status_code=400, detail="Location is required.")
    if len(about_applicant) < 20:
        raise HTTPException(status_code=400, detail="About applicant must be at least 20 characters long.")

    if not jobOpening_id or not jobOpening_id.strip():
        raise HTTPException(status_code=400, detail="Job opening ID is required.")
    try:
        opening_uuid = uuid.UUID(jobOpening_id.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job opening UUID format.")

    # Verify opening exists and is active
    opening = session.exec(
        select(JobOpenings).where(
            JobOpenings.id == opening_uuid,
            JobOpenings.is_active == True,
            JobOpenings.is_delete == False,
        )
    ).first()
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found or is no longer active.")

    # Duplicate check – same email per opening
    existing = session.exec(
        select(JobApplications).where(
            JobApplications.jobOpening_id == opening_uuid,
            func.lower(JobApplications.email) == email.lower(),
            JobApplications.is_delete == False,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An application with this email already exists for this job opening.")

    # Validate and save resume PDF
    if resume is None or isinstance(resume, str):
        raise HTTPException(status_code=400, detail="Resume PDF is required.")
    if not hasattr(resume, "filename") or not resume.filename:
        raise HTTPException(status_code=400, detail="Resume PDF is required.")

    resume_filename = None
    try:
        resume_filename = await process_and_save_resume(resume, name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing resume: {str(e)}")

    if not resume_filename:
        raise HTTPException(status_code=500, detail="Failed to save resume file.")

    application = JobApplications(
        name=name,
        email=email,
        phone=phone,
        location=location,
        portfolio_link=portfolio_link.strip() if portfolio_link else None,
        jobOpening_id=opening_uuid,
        about_applicant=about_applicant,
        resume=resume_filename,
    )

    session.add(application)
    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        if resume_filename:
            resume_path = settings.UPLOAD_DIR_PDF / "job_applications" / resume_filename
            cleanup_pdf(resume_path)
        raise HTTPException(status_code=400, detail="Database integrity error. Please check your data.")

    session.refresh(application)
    return {"id": str(application.id), "message": "Job application submitted successfully."}


def jobApplicationUpdateStatus(
        application_id: uuid.UUID,
        status: str,
        session: Session,
        is_reviewed: Optional[bool] = None,
):
    application = getJobApplicationById(session, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Job application not found.")

    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

    application.status = status
    if is_reviewed is not None:
        application.is_reviewed = is_reviewed
    elif status != ApplicationStatus.PENDING.value:
        application.is_reviewed = True

    session.add(application)
    session.commit()
    session.refresh(application)
    return {"id": str(application.id), "message": "Application status updated successfully."}


def jobApplicationSoftDelete(application_id: uuid.UUID, session: Session):
    application = getJobApplicationById(session, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Job application not found.")
    application.is_delete = True
    session.add(application)
    session.commit()
    return {"id": str(application_id), "message": "Job application deleted successfully."}
