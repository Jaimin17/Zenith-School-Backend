import uuid
from datetime import date, datetime
from typing import Optional, List

from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import func
from sqlmodel import Session, select

from models import AcademicYear, Student, StudentClassHistory, StudentStatus, Teacher, Parent
from repository.teacherClassHistory import seedTeacherClassHistoryToAcademicYear
from schemas import AcademicYearCreate, AcademicYearUpdate, PaginatedAcademicYearResponse
from core.config import settings


def getActiveAcademicYear(session: Session) -> Optional[AcademicYear]:
    query = select(AcademicYear).where(
        AcademicYear.is_active == True,
        AcademicYear.is_delete == False,
    )
    return session.exec(query).first()


def ensureSelectedAcademicYearIsMutable(request: Request, session: Session) -> Optional[AcademicYear]:
    selected_year_id = request.cookies.get("selected_year_id")
    if not selected_year_id:
        print("selected_year_id not found ", getActiveAcademicYear(session))
        return getActiveAcademicYear(session)

    try:
        year_uuid = uuid.UUID(selected_year_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Selected academic year is invalid.")

    selected_year = getAcademicYearById(year_uuid, session)
    if not selected_year:
        raise HTTPException(status_code=404, detail="Selected academic year not found.")

    active_year = getActiveAcademicYear(session)
    if active_year and selected_year.id != active_year.id:
        raise HTTPException(
            status_code=403,
            detail="Past academic years are read-only. Switch to the active year to make changes.",
        )

    print("selected_year ", selected_year)

    return selected_year


def getAcademicYearById(year_id: uuid.UUID, session: Session) -> Optional[AcademicYear]:
    query = select(AcademicYear).where(
        AcademicYear.id == year_id,
        AcademicYear.is_delete == False,
    )
    return session.exec(query).first()


def getAllAcademicYears(session: Session, page: int) -> PaginatedAcademicYearResponse:
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = select(func.count(AcademicYear.id)).where(AcademicYear.is_delete == False)
    total_count = session.exec(count_query).one()

    query = (
        select(AcademicYear)
        .where(AcademicYear.is_delete == False)
        .order_by(AcademicYear.start_date.desc())
        .offset(offset_value)
        .limit(settings.ITEMS_PER_PAGE)
    )
    years = session.exec(query).all()

    total_pages = max(1, (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE)

    return PaginatedAcademicYearResponse(
        data=years,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def getVisibleAcademicYears(user, role: str, session: Session) -> List[AcademicYear]:
    """Return academic years visible to the calling user based on their role."""
    base_query = (
        select(AcademicYear)
        .where(AcademicYear.is_delete == False)
        .order_by(AcademicYear.start_date.desc())
    )
    if role == "admin":
        return session.exec(base_query).all()
    elif role == "teacher":
        # Years that started on or after the teacher's account was created
        hire_date = user.created_at.date() if hasattr(user.created_at, 'date') else user.created_at
        return session.exec(
            base_query.where(AcademicYear.start_date >= hire_date)
        ).all()
    elif role == "student":
        # Only years the student has a history record for
        year_ids = session.exec(
            select(StudentClassHistory.academic_year_id)
            .where(StudentClassHistory.student_id == user.id)
        ).all()
        if not year_ids:
            return []
        return session.exec(
            base_query.where(AcademicYear.id.in_(year_ids))
        ).all()
    elif role == "parent":
        # Years where at least one child has a history record
        child_ids = session.exec(
            select(Student.id).where(
                Student.parent_id == user.id,
                Student.is_delete == False,
            )
        ).all()
        if not child_ids:
            return []
        year_ids = session.exec(
            select(StudentClassHistory.academic_year_id)
            .where(StudentClassHistory.student_id.in_(child_ids))
        ).all()
        if not year_ids:
            return []
        return session.exec(
            base_query.where(AcademicYear.id.in_(year_ids))
        ).all()
    return session.exec(base_query).all()


def getAllAcademicYearsUnpaginated(session: Session) -> List[AcademicYear]:
    query = (
        select(AcademicYear)
        .where(AcademicYear.is_delete == False)
        .order_by(AcademicYear.start_date.desc())
    )
    return session.exec(query).all()


def createAcademicYear(data: AcademicYearCreate, session: Session) -> AcademicYear:
    if data.start_date >= data.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    # Check for year_label uniqueness
    existing_label = session.exec(
        select(AcademicYear).where(
            AcademicYear.year_label == data.year_label.strip(),
            AcademicYear.is_delete == False,
        )
    ).first()
    if existing_label:
        raise HTTPException(status_code=409, detail=f"Academic year '{data.year_label}' already exists.")

    # Check for date-range overlap with existing non-deleted years
    overlap = session.exec(
        select(AcademicYear).where(
            AcademicYear.is_delete == False,
            AcademicYear.start_date < data.end_date,
            AcademicYear.end_date > data.start_date,
        )
    ).first()
    if overlap:
        raise HTTPException(
            status_code=409,
            detail=f"Date range overlaps with existing academic year '{overlap.year_label}'.",
        )

    new_year = AcademicYear(
        year_label=data.year_label.strip(),
        start_date=data.start_date,
        end_date=data.end_date,
        is_active=False,
        is_delete=False,
    )
    session.add(new_year)
    session.commit()
    session.refresh(new_year)
    return new_year


def activateAcademicYear(year_id: uuid.UUID, session: Session) -> AcademicYear:
    previous_active = getActiveAcademicYear(session)
    target = session.exec(
        select(AcademicYear).where(
            AcademicYear.id == year_id,
            AcademicYear.is_delete == False,
        )
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Academic year not found.")

    # Atomically deactivate all others, activate target
    all_active = session.exec(
        select(AcademicYear).where(AcademicYear.is_active == True)
    ).all()
    for y in all_active:
        y.is_active = False
        session.add(y)

    target.is_active = True
    session.add(target)

    # Snapshot teacher-class history for the year being closed (previous active year).
    if previous_active and previous_active.id != target.id:
        seedTeacherClassHistoryToAcademicYear(previous_active.id, session)

    # Sync all students' grade_id / class_id / status from their history record for this year
    histories = session.exec(
        select(StudentClassHistory).where(StudentClassHistory.academic_year_id == year_id)
    ).all()
    for history in histories:
        student = session.get(Student, history.student_id)
        if not student or student.is_delete:
            continue
        if history.grade_id is None:
            student.status = StudentStatus.GRADUATED
            student.grade_id = None
            student.class_id = None
        else:
            student.grade_id = history.grade_id
            student.class_id = history.class_id
            student.status = StudentStatus.ACTIVE
        session.add(student)

    session.commit()
    session.refresh(target)
    return target


def updateAcademicYear(year_id: uuid.UUID, data: AcademicYearUpdate, session: Session) -> AcademicYear:
    year = getAcademicYearById(year_id, session)
    if not year:
        raise HTTPException(status_code=404, detail="Academic year not found.")

    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        return year

    start = update_data.get("start_date", year.start_date)
    end = update_data.get("end_date", year.end_date)
    if start >= end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    if "year_label" in update_data:
        existing = session.exec(
            select(AcademicYear).where(
                AcademicYear.year_label == update_data["year_label"].strip(),
                AcademicYear.is_delete == False,
                AcademicYear.id != year_id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Academic year '{update_data['year_label']}' already exists.")
        update_data["year_label"] = update_data["year_label"].strip()

    overlap = session.exec(
        select(AcademicYear).where(
            AcademicYear.is_delete == False,
            AcademicYear.id != year_id,
            AcademicYear.start_date < end,
            AcademicYear.end_date > start,
        )
    ).first()
    if overlap:
        raise HTTPException(
            status_code=409,
            detail=f"Date range overlaps with existing academic year '{overlap.year_label}'.",
        )

    for key, value in update_data.items():
        setattr(year, key, value)
    session.add(year)
    session.commit()
    session.refresh(year)
    return year
