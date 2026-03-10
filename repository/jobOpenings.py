import uuid
from datetime import date
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import JobOpenings, JobApplications, JobType
from schemas import PaginatedJobOpeningResponse, JobOpeningRead

JOB_VALID_TYPES = [jt.value for jt in JobType]


def _add_search_option(query: Select, search: Optional[str]):
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(JobOpenings.title).like(pattern) |
            func.lower(JobOpenings.description).like(pattern) |
            func.lower(JobOpenings.location).like(pattern)
        )
    return query


def getAllJobOpenings(session: Session, search: Optional[str], page: int, active_only: bool = False):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = select(func.count(JobOpenings.id.distinct())).where(JobOpenings.is_delete == False)
    if active_only:
        count_query = count_query.where(JobOpenings.is_active == True)
    count_query = _add_search_option(count_query, search)
    total_count = session.exec(count_query).one()

    query = select(JobOpenings).where(JobOpenings.is_delete == False)
    if active_only:
        query = query.where(JobOpenings.is_active == True)
    query = _add_search_option(query, search)
    query = query.order_by(JobOpenings.created_at.desc()).offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    openings = session.exec(query).all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    results = []
    for opening in openings:
        count = session.exec(
            select(func.count(JobApplications.id)).where(
                JobApplications.jobOpening_id == opening.id,
                JobApplications.is_delete == False
            )
        ).one()
        data = JobOpeningRead.model_validate(opening)
        data.total_applications = count
        results.append(data)

    return PaginatedJobOpeningResponse(
        data=results,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def getActiveJobOpenings(session: Session, search: Optional[str], page: int):
    return getAllJobOpenings(session, search, page, active_only=True)


def getJobOpeningById(session: Session, opening_id: uuid.UUID, public: bool = False):
    query = select(JobOpenings).where(
        JobOpenings.id == opening_id,
        JobOpenings.is_delete == False
    )
    if public:
        query = query.where(JobOpenings.is_active == True)
    return session.exec(query).first()


async def jobOpeningSave(
        title: str,
        description: str,
        experience: int,
        positions: int,
        job_type: str,
        is_active: bool,
        session: Session,
        location: Optional[str] = None,
        salary_range: Optional[str] = None,
        deadline: Optional[date] = None,
        subject_id: Optional[str] = None,
):
    title = title.strip()
    description = description.strip()

    if len(title) < 3:
        raise HTTPException(status_code=400, detail="Title must be at least 3 characters long.")
    if len(description) < 10:
        raise HTTPException(status_code=400, detail="Description must be at least 10 characters long.")
    if experience < 0:
        raise HTTPException(status_code=400, detail="Experience cannot be negative.")
    if positions < 1:
        raise HTTPException(status_code=400, detail="Positions must be at least 1.")
    if job_type not in JOB_VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid job type. Must be one of: {JOB_VALID_TYPES}")

    duplicate = session.exec(
        select(JobOpenings).where(
            func.lower(func.trim(JobOpenings.title)) == title.lower(),
            JobOpenings.is_delete == False
        )
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"A job opening with the title '{title}' already exists.")

    subject_uuid: Optional[uuid.UUID] = None
    if subject_id and subject_id.strip():
        try:
            subject_uuid = uuid.UUID(subject_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid subject UUID format.")

    opening = JobOpenings(
        title=title,
        description=description,
        experience=experience,
        positions=positions,
        location=location.strip() if location else None,
        salary_range=salary_range.strip() if salary_range else None,
        deadline=deadline,
        job_type=job_type,
        subject_id=subject_uuid,
        is_active=is_active,
    )

    session.add(opening)
    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error. Please check your data.")

    session.refresh(opening)
    return {"id": str(opening.id), "message": "Job opening created successfully."}


async def jobOpeningUpdate(
        opening_id: uuid.UUID,
        title: str,
        description: str,
        experience: int,
        positions: int,
        job_type: str,
        is_active: bool,
        session: Session,
        location: Optional[str] = None,
        salary_range: Optional[str] = None,
        deadline: Optional[date] = None,
        subject_id: Optional[str] = None,
):
    opening = getJobOpeningById(session, opening_id)
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found.")

    title = title.strip()
    description = description.strip()

    if len(title) < 3:
        raise HTTPException(status_code=400, detail="Title must be at least 3 characters long.")
    if len(description) < 10:
        raise HTTPException(status_code=400, detail="Description must be at least 10 characters long.")
    if experience < 0:
        raise HTTPException(status_code=400, detail="Experience cannot be negative.")
    if positions < 1:
        raise HTTPException(status_code=400, detail="Positions must be at least 1.")
    if job_type not in JOB_VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid job type. Must be one of: {JOB_VALID_TYPES}")

    duplicate = session.exec(
        select(JobOpenings).where(
            func.lower(func.trim(JobOpenings.title)) == title.lower(),
            JobOpenings.is_delete == False,
            JobOpenings.id != opening_id
        )
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"A job opening with the title '{title}' already exists.")

    subject_uuid: Optional[uuid.UUID] = None
    if subject_id and subject_id.strip():
        try:
            subject_uuid = uuid.UUID(subject_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid subject UUID format.")

    opening.title = title
    opening.description = description
    opening.experience = experience
    opening.positions = positions
    opening.location = location.strip() if location else None
    opening.salary_range = salary_range.strip() if salary_range else None
    opening.deadline = deadline
    opening.job_type = job_type
    opening.subject_id = subject_uuid
    opening.is_active = is_active

    session.add(opening)
    try:
        session.flush()
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error. Please check your data.")

    session.refresh(opening)
    return {"id": str(opening.id), "message": "Job opening updated successfully."}


def jobOpeningToggleActive(opening_id: uuid.UUID, session: Session):
    opening = getJobOpeningById(session, opening_id)
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    opening.is_active = not opening.is_active
    session.add(opening)
    session.commit()
    session.refresh(opening)
    status_label = "activated" if opening.is_active else "deactivated"
    return {"id": str(opening.id), "message": f"Job opening {status_label} successfully."}


def jobOpeningSoftDelete(opening_id: uuid.UUID, session: Session):
    opening = getJobOpeningById(session, opening_id)
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    opening.is_delete = True
    opening.is_active = False
    session.add(opening)
    session.commit()
    return {"id": str(opening_id), "message": "Job opening deleted successfully."}
