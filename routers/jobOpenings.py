import uuid
from datetime import date
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from core.database import SessionDep
from deps import AdminUser
from repository.jobOpenings import (
    getAllJobOpenings,
    getActiveJobOpenings,
    getJobOpeningById,
    jobOpeningSave,
    jobOpeningUpdate,
    jobOpeningToggleActive,
    jobOpeningSoftDelete,
)
from schemas import JobOpeningRead, PaginatedJobOpeningResponse, SaveResponse

router = APIRouter(prefix="/job-openings")


# --- Public --------------------------------------------------------------------

@router.get("/public", response_model=PaginatedJobOpeningResponse)
def listActiveJobOpenings(session: SessionDep, search: str = None, page: int = 1):
    """Public – active job openings for the portal."""
    return getActiveJobOpenings(session, search, page)


@router.get("/public/{opening_id}", response_model=JobOpeningRead)
def getPublicJobOpeningDetail(opening_id: uuid.UUID, session: SessionDep):
    """Public – single active job opening detail."""
    opening = getJobOpeningById(session, opening_id, public=True)
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    return opening


# --- Admin ---------------------------------------------------------------------

@router.get("/getAll", response_model=PaginatedJobOpeningResponse)
def listAllJobOpenings(
        current_user: AdminUser,
        session: SessionDep,
        search: str = None,
        page: int = 1,
):
    """Admin – all job openings including inactive."""
    return getAllJobOpenings(session, search, page)


@router.get("/getById/{opening_id}", response_model=JobOpeningRead)
def getJobOpeningDetail(opening_id: uuid.UUID, current_user: AdminUser, session: SessionDep):
    """Admin – get single job opening by ID."""
    opening = getJobOpeningById(session, opening_id)
    if not opening:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    return opening


@router.post("/save", response_model=SaveResponse)
async def saveJobOpening(
        current_user: AdminUser,
        session: SessionDep,
        title: str = Form(...),
        description: str = Form(...),
        experience: int = Form(0),
        positions: int = Form(1),
        job_type: str = Form("full_time"),
        is_active: bool = Form(True),
        location: Optional[str] = Form(None),
        salary_range: Optional[str] = Form(None),
        deadline: Optional[date] = Form(None),
        subject_id: Optional[str] = Form(None),
):
    """Admin – create a new job opening."""
    return await jobOpeningSave(
        title=title,
        description=description,
        experience=experience,
        positions=positions,
        job_type=job_type,
        is_active=is_active,
        session=session,
        location=location,
        salary_range=salary_range,
        deadline=deadline,
        subject_id=subject_id,
    )


@router.put("/update", response_model=SaveResponse)
async def updateJobOpening(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        experience: int = Form(0),
        positions: int = Form(1),
        job_type: str = Form("full_time"),
        is_active: bool = Form(True),
        location: Optional[str] = Form(None),
        salary_range: Optional[str] = Form(None),
        deadline: Optional[date] = Form(None),
        subject_id: Optional[str] = Form(None),
):
    """Admin – update an existing job opening."""
    try:
        opening_uuid = uuid.UUID(id.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job opening UUID format.")

    return await jobOpeningUpdate(
        opening_id=opening_uuid,
        title=title,
        description=description,
        experience=experience,
        positions=positions,
        job_type=job_type,
        is_active=is_active,
        session=session,
        location=location,
        salary_range=salary_range,
        deadline=deadline,
        subject_id=subject_id,
    )


@router.patch("/toggle-active", response_model=SaveResponse)
def toggleJobOpeningActive(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    """Admin – toggle is_active on a job opening."""
    return jobOpeningToggleActive(id, session)


@router.delete("/delete", response_model=SaveResponse)
def deleteJobOpening(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    """Admin – soft-delete a job opening."""
    return jobOpeningSoftDelete(id, session)
