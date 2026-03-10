import uuid
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Form, UploadFile, File

from core.database import SessionDep
from deps import AdminUser
from repository.jobApplications import (
    getAllJobApplications,
    getJobApplicationById,
    jobApplicationSave,
    jobApplicationUpdateStatus,
    jobApplicationSoftDelete,
)
from schemas import (
    JobApplicationRead,
    JobApplicationDetail,
    PaginatedJobApplicationResponse,
    SaveResponse,
)

router = APIRouter(prefix="/job-applications")


# ─── Public ────────────────────────────────────────────────────────────────────

@router.post("/save", response_model=SaveResponse)
async def submitJobApplication(
        session: SessionDep,
        name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        location: str = Form(...),
        jobOpening_id: str = Form(...),
        about_applicant: str = Form(...),
        resume: Union[UploadFile, str] = File(...),
        portfolio_link: Optional[str] = Form(None),
):
    """
    Public – submit a job application.
    Resume must be a valid PDF file (max 10 MB).
    """
    processed_resume = None
    if resume is not None and not isinstance(resume, str):
        if hasattr(resume, "filename") and resume.filename:
            processed_resume = resume

    if not processed_resume:
        raise HTTPException(status_code=400, detail="Resume PDF file is required.")

    return await jobApplicationSave(
        name=name,
        email=email,
        phone=phone,
        location=location,
        jobOpening_id=jobOpening_id,
        about_applicant=about_applicant,
        resume=processed_resume,
        session=session,
        portfolio_link=portfolio_link,
    )


# ─── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/getAll", response_model=PaginatedJobApplicationResponse)
def listAllJobApplications(
        current_user: AdminUser,
        session: SessionDep,
        search: str = None,
        page: int = 1,
        opening_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        is_reviewed: Optional[bool] = None,
):
    """
    Admin – list all job applications.
    Optional filters: opening_id, status (pending/reviewed/accepted/rejected), is_reviewed.
    """
    return getAllJobApplications(session, search, page, opening_id, status, is_reviewed)


@router.get("/getById/{application_id}", response_model=JobApplicationDetail)
def getJobApplicationDetail(application_id: uuid.UUID, current_user: AdminUser, session: SessionDep):
    """Admin – get a single application with its linked job opening."""
    application = getJobApplicationById(session, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Job application not found.")
    return application


@router.patch("/update-status", response_model=SaveResponse)
def updateApplicationStatus(
        current_user: AdminUser,
        session: SessionDep,
        id: uuid.UUID = Form(...),
        status: str = Form(...),
        is_reviewed: Optional[bool] = Form(None),
):
    """
    Admin – update application status.
    Valid values: pending, reviewed, accepted, rejected.
    is_reviewed is auto-set True when status is not pending.
    """
    return jobApplicationUpdateStatus(id, status, session, is_reviewed)


@router.delete("/delete", response_model=SaveResponse)
def deleteJobApplication(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    """Admin – soft-delete a job application."""
    return jobApplicationSoftDelete(id, session)
