import uuid
from typing import List

from fastapi import APIRouter, Query

from core.database import SessionDep
from deps import AdminUser, CurrentUser
from repository.academicYear import (
    getAllAcademicYears,
    getAllAcademicYearsUnpaginated,
    getVisibleAcademicYears,
    getAcademicYearById,
    createAcademicYear,
    activateAcademicYear,
    getActiveAcademicYear, updateAcademicYear,
)
from repository.studentClassHistory import getStudentFullHistory, seedStudentsToAcademicYear
from schemas import (
    AcademicYearBase,
    AcademicYearCreate,
    PaginatedAcademicYearResponse,
    StudentHistoryResponse, AcademicYearUpdate,
    SeedStudentsResponse,
)

router = APIRouter(prefix="/academic-years")


@router.get("/visible", response_model=List[AcademicYearBase])
def listVisibleAcademicYears(current_user: CurrentUser, session: SessionDep):
    """Return academic years visible to the calling user (role-scoped)."""
    user, role = current_user
    return getVisibleAcademicYears(user, role, session)


@router.get("/all", response_model=List[AcademicYearBase])
def listAllAcademicYears(current_user: CurrentUser, session: SessionDep):
    """Return all academic years (unpaginated) — used for dropdowns."""
    return getAllAcademicYearsUnpaginated(session)


@router.get("/", response_model=PaginatedAcademicYearResponse)
def listAcademicYears(
    current_user: AdminUser,
    session: SessionDep,
    page: int = Query(1, ge=1),
):
    """Admin paginated list of all academic years."""
    return getAllAcademicYears(session, page)


@router.get("/active", response_model=AcademicYearBase)
def getActive(current_user: CurrentUser, session: SessionDep):
    """Return the currently active academic year."""
    year = getActiveAcademicYear(session)
    if not year:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No active academic year found.")
    return year


@router.get("/{year_id}", response_model=AcademicYearBase)
def getAcademicYear(year_id: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    year = getAcademicYearById(year_id, session)
    if not year:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Academic year not found.")
    return year


@router.post("/", response_model=AcademicYearBase, status_code=201)
def createYear(data: AcademicYearCreate, current_user: AdminUser, session: SessionDep):
    """Create a new academic year. Validates no date overlap. Not active by default."""
    return createAcademicYear(data, session)


@router.patch("/{year_id}/activate", response_model=AcademicYearBase)
def activateYear(year_id: uuid.UUID, current_user: AdminUser, session: SessionDep):
    """Set this year as active. Atomically deactivates all other years."""
    return activateAcademicYear(year_id, session)


@router.patch("/{year_id}", response_model=AcademicYearBase)
def updateYear(year_id: uuid.UUID, data: AcademicYearUpdate, current_user: AdminUser, session: SessionDep):
    """Update an academic year's label or date range."""
    return updateAcademicYear(year_id, data, session)


@router.post("/{year_id}/seed-students", response_model=SeedStudentsResponse)
def seedStudents(year_id: uuid.UUID, current_user: AdminUser, session: SessionDep):
    """Bulk-create StudentClassHistory records for all active students in this academic year.
    Idempotent — students already enrolled are skipped."""
    return seedStudentsToAcademicYear(year_id, session)
