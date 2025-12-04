import uuid
from datetime import datetime, date, timezone
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, AdminUser
from repository.events import getAllEventsIsDeleteFalse, getAllEventsByTeacherAndIsDeleteFalse, \
    getAllEventsByStudentAndIsDeleteFalse, getAllEventsByParentAndIsDeleteFalse, getAllEventsByDate, eventSave, \
    eventUpdate, EventSoftDelete
from schemas import EventRead, EventBase, SaveResponse, EventSave, EventUpdate

router = APIRouter(
    prefix="/events",
)


@router.get("/getAll", response_model=List[EventRead])
def getAllEvents(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_events = getAllEventsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_events = getAllEventsByTeacherAndIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_events = getAllEventsByStudentAndIsDeleteFalse(user.id, session, search, page)
    else:
        all_events = getAllEventsByParentAndIsDeleteFalse(user.id, session, search, page)
    return all_events


@router.get("/getAllByDate", response_model=List[EventBase])
def getAllByDate(current_user: AdminUser, session: SessionDep, selectDate: str | None = None):
    searchDate = date.fromisoformat(selectDate) if selectDate is not None else date.today()
    print(f"Search Date is: {searchDate}")
    events = getAllEventsByDate(session, searchDate)
    return events


@router.post("/save", response_model=SaveResponse)
def saveEvents(event: EventSave, current_user: AdminUser, session: SessionDep):
    user, role = current_user

    if not event.title or len(event.title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if not event.description or len(event.description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    if not event.start_time:
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not event.end_time:
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if event.start_time >= event.end_time:
        raise HTTPException(
            status_code=400,
            detail="Event start time must be before end time."
        )

    event_start = event.start_time
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=timezone.utc)

    if event_start < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Event start time cannot be in the past."
        )

    result = eventSave(event, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateEvent(current_user: AdminUser, event: EventUpdate, session: SessionDep):
    user, role = current_user

    if not event.id:
        raise HTTPException(
            status_code=400,
            detail="Event ID is required for updating."
        )

    if not event.title or len(event.title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if not event.description or len(event.description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    if not event.start_time:
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not event.end_time:
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if event.start_time >= event.end_time:
        raise HTTPException(
            status_code=400,
            detail="Event start time must be before end time."
        )

    event_start = event.start_time
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=timezone.utc)

    if event_start < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Event start time cannot be in the past."
        )

    result = eventUpdate(event, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def softDeleteEvent(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    user, role = current_user

    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Event ID is required for deleting."
        )

    result = EventSoftDelete(id, session)
    return result
