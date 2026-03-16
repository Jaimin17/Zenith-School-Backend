import uuid
from datetime import datetime, date, timezone
from typing import List, Optional, Union

from fastapi.params import Form
from sqlalchemy import select

from core.database import SessionDep
from fastapi import APIRouter, HTTPException, UploadFile, File
from deps import CurrentUser, AllUser, AdminUser
from models import StudentClassHistory, Student
from repository.events import getAllEventsIsDeleteFalse, getAllEventsByTeacherAndIsDeleteFalse, \
    getAllEventsByStudentAndIsDeleteFalse, getAllEventsByParentAndIsDeleteFalse, getAllEventsByDate, eventSave, \
    eventUpdate, EventSoftDelete, getEventById, getAllPublicEventsAndIsDeleteFalse
from schemas import EventRead, EventBase, SaveResponse, EventSave, EventUpdate, PaginatedEventResponse

router = APIRouter(
    prefix="/events",
)


@router.get("/getAll", response_model=PaginatedEventResponse)
def getAllEvents(current_user: AllUser, session: SessionDep, student_id: Optional[uuid.UUID] = None,
                 search: str = None, page: int = 1,
                 from_date: Optional[date] = None, to_date: Optional[date] = None):
    user, role = current_user
    if role == "admin":
        all_events = getAllEventsIsDeleteFalse(session, search, page, from_date, to_date)
    elif role == "teacher":
        all_events = getAllEventsByTeacherAndIsDeleteFalse(user.id, session, search, page, from_date, to_date)
    # elif role == "student":
    #     all_events = getAllEventsByStudentAndIsDeleteFalse(user.id, session, search, page, from_date, to_date)
    # else:
    #     all_events = getAllEventsByParentAndIsDeleteFalse(user.id, session, search, page, from_date, to_date)
    else:
        if role == "parent":
            if not student_id:
                raise HTTPException(
                    status_code=400,
                    detail="Student Id is mandatory, provide correct student ID."
                )

            check_student_permission_query = (
                select(Student)
                .where(
                    Student.id == student_id,
                    Student.parent_id == user.id,
                    Student.is_delete == False
                )
            )

            check_student_permission = session.exec(check_student_permission_query).first()
            if not check_student_permission:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to access this Event."
                )

        all_events = getAllEventsByStudentAndIsDeleteFalse(student_id, session, search, page, from_date, to_date)

    return all_events


@router.get("/getAllPublicEvents", response_model=PaginatedEventResponse)
def getAllPublicEvents(session: SessionDep, page: int = 1):
    all_events = getAllPublicEventsAndIsDeleteFalse(session, page)
    return all_events


@router.get("/getPublicEventById/{eventId}", response_model=EventRead)
def getPublicEventById(eventId: uuid.UUID, session: SessionDep):
    event_detail = getEventById(session, eventId)

    if not event_detail:
        raise HTTPException(
            status_code=404,
            detail="Event not found with provided ID."
        )

    return event_detail


@router.get("/getById/{eventId}", response_model=EventRead)
def getById(eventId: uuid.UUID, current_user: AllUser, session: SessionDep):
    user, role = current_user

    event_detail = getEventById(session, eventId)

    if not event_detail:
        raise HTTPException(
            status_code=404,
            detail="Event not found with provided ID."
        )

    if not event_detail.class_id:
        return event_detail

    if role.lower() == "admin":
        return event_detail

    elif role.lower() == "teacher":
        if event_detail.related_class and event_detail.related_class.supervisor_id == user.id:
            return event_detail
        else:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this Event."
            )

    elif role.lower() == "student":
        if event_detail.related_class is None:
            raise HTTPException(
                status_code=500,
                detail="Event class data is missing."
            )

        check_student_permission_query = (
            select(StudentClassHistory)
            .where(
                StudentClassHistory.class_id == event_detail.class_id,
                StudentClassHistory.student_id == user.id
            )
        )

        check_student_permission = session.exec(check_student_permission_query).first()

        if not check_student_permission:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this event."
            )

        return event_detail

    elif role.lower() == "parent":
        if event_detail.related_class is None:
            raise HTTPException(
                status_code=500,
                detail="Event class data is missing."
            )

        if not user.students:
            raise HTTPException(
                status_code=403,
                detail="No students associated with your account."
            )

        class_student_ids = [s.id for s in event_detail.related_class.students if not s.is_delete]
        parent_student_ids = [s.id for s in user.students if not s.is_delete]

        # Check if any of parent's students are in the class
        has_access = any(student_id in class_student_ids for student_id in parent_student_ids)

        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="None of your children have access to this event."
            )

        return event_detail

    else:
        raise HTTPException(
            status_code=403,
            detail="Invalid user role."
        )


@router.get("/getAllByDate", response_model=List[EventBase])
def getAllByDate(current_user: AllUser, session: SessionDep, selectDate: str | None = None):
    searchDate = date.fromisoformat(selectDate) if selectDate is not None else date.today()
    print(f"Search Date is: {searchDate}")

    user, role = current_user

    events = getAllEventsByDate(session, searchDate, user, role)
    return events


@router.post("/save", response_model=SaveResponse)
async def saveEvents(
        current_user: AdminUser,
        session: SessionDep,
        title: str = Form(...),
        description: str = Form(...),
        img: list[Union[str, UploadFile]] = File(...),
        start_time: datetime = Form(...),
        end_time: datetime = Form(...),
        class_id: Optional[str] = Form(None)
):
    user, role = current_user

    if not title or len(title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if not description or len(description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    if not start_time:
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not end_time:
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="Event start time must be before end time."
        )

    event_start = start_time
    # if event_start.tzinfo is None:
    #     event_start = event_start.replace(tzinfo=timezone.utc)

    # if event_start < datetime.now(timezone.utc):
    if event_start < datetime.now():
        raise HTTPException(
            status_code=400,
            detail="Event start time cannot be in the past."
        )

    classId = None
    if class_id:
        try:
            classId = uuid.UUID(class_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="class Id is not a valid type."
            )

    processed_imgs: list[UploadFile] = [
        image for image in img
        if image is not None and not isinstance(image, str)
           and hasattr(image, 'filename') and hasattr(image, 'file') and image.filename
    ]

    if not processed_imgs:
        raise HTTPException(
            status_code=400,
            detail="At least one valid image file must be uploaded."
        )

    event_data: EventSave = EventSave(
        title=title.strip(),
        description=description.strip(),
        start_time=event_start,
        end_time=end_time,
        class_id=classId
    )

    result = await eventSave(event_data, processed_imgs, session)
    return result


@router.put("/update", response_model=SaveResponse)
async def updateEvent(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        start_time: datetime = Form(...),
        end_time: datetime = Form(...),
        class_id: Optional[str] = Form(None),
        img: list[Union[str, UploadFile]] = File(default=[])
):
    user, role = current_user

    if not id:
        raise HTTPException(
            status_code=400,
            detail="Event ID is required for updating."
        )
    else:
        try:
            ID = uuid.UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Event ID is not a valid type."
            )

    if not title or len(title.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Title should be at least 3 characters long."
        )

    if not description or len(description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description should be at least 10 characters long."
        )

    if not start_time:
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not end_time:
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="Event start time must be before end time."
        )

    event_start = start_time
    # if event_start.tzinfo is None:
    #     event_start = event_start.replace(tzinfo=timezone.utc)

    classId = None
    if class_id:
        try:
            classId = uuid.UUID(class_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="class Id is not a valid type."
            )

    processed_imgs: list[UploadFile] = [
        image for image in img
        if image is not None and not isinstance(image, str)
           and hasattr(image, 'filename') and hasattr(image, 'file') and image.filename
    ]

    event_data: EventUpdate = EventUpdate(
        id=ID,
        title=title.strip(),
        description=description.strip(),
        start_time=event_start,
        end_time=end_time,
        class_id=classId
    )

    result = await eventUpdate(event_data, processed_imgs, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def softDeleteEvent(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = EventSoftDelete(id, session)
    return result
