import uuid
from datetime import date, datetime
from typing import List, Optional, Union
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi import APIRouter, HTTPException, Form, UploadFile, File, Depends

from core.config import settings
from deps import CurrentUser, TeacherOrAdminUser, AdminUser, AllUser
from core.database import SessionDep
from models import UserSex
from repository.teacher import getAllTeachersIsDeleteFalse, getAllTeachersOfClassAndIsDeleteFalse, countTeacher, \
    findTeacherById, TeacherUpdate, teacherSoftDeleteWithLessonAndClassAndSubject, teacherSaveWithImage, \
    getTotalTeachersCount, getAllTeachersListIsDeleteFalse
from schemas import TeacherRead, SaveResponse, TeacherDeleteResponse, PaginatedTeacherResponse, TeacherBase

router = APIRouter(
    prefix="/teacher",
)


@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countTeacher(session)


@router.get("/getAll", response_model=PaginatedTeacherResponse)
def getAllTeachers(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    all_teachers = getAllTeachersIsDeleteFalse(session, search, page)

    total_count = getTotalTeachersCount(session, search)

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE
    has_next = page < total_pages
    has_prev = page > 1
    return PaginatedTeacherResponse(
        data=all_teachers,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )

@router.get("/getFullList", response_model=List[TeacherBase])
def getFullTeacherList(current_user: AllUser, session: SessionDep):
    all_teachers = getAllTeachersListIsDeleteFalse(session)

    return all_teachers


@router.get("/{classId}", response_model=PaginatedTeacherResponse)
def getTeacherByClassId(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                        page: int = 1):
    all_teachers = getAllTeachersOfClassAndIsDeleteFalse(classId, session, search, page)
    return all_teachers


@router.get("/get/{teacherId}", response_model=TeacherRead)
def getTeacherById(teacherId: uuid.UUID, current_user: AdminUser, session: SessionDep):
    teacher = findTeacherById(teacherId, session)
    return teacher


@router.post("/save", response_model=SaveResponse)
async def saveTeacher(
        current_user: AdminUser,
        session: SessionDep,
        username: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        address: str = Form(...),
        blood_type: str = Form(...),
        sex: str = Form(...),
        dob: date = Form(...),  # Pydantic/FastAPI handles date conversion
        subjects: str = Form(...),
        img: Union[UploadFile, str, None] = File(None)
):
    try:
        subject_ids = [
            uuid.UUID(s.strip())
            for s in subjects.split(',')
            if s.strip()
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subject UUID format: {str(e)}"
        )

        # Validate subjects list is not empty
    if not subject_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one subject must be assigned to the teacher."
        )

    try:
        sex_enum = UserSex(sex.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid sex value. Must be 'male' or 'female'."
        )

        # Validate phone format
    if not settings.PHONE_RE.match(phone.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid Indian phone number. Must be 10 digits starting with 6-9."
        )

    processed_img: Optional[UploadFile] = None
    if img is not None and not isinstance(img, str):
        # Check if it has the attributes of an UploadFile (duck typing)
        if hasattr(img, 'filename') and hasattr(img, 'file') and img.filename:
            processed_img = img
    elif isinstance(img, str) and img.strip():
        # If somehow a non-empty string is passed, treat as no image
        processed_img = None

    teacher_data = {
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "address": address,
        "blood_type": blood_type,
        "sex": sex_enum,
        "dob": dob,
        "subjects": subject_ids
    }

    result = await teacherSaveWithImage(teacher_data, processed_img, session)
    return result


@router.put("/update", response_model=SaveResponse)
async def updateTeacher(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        username: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        address: str = Form(...),
        blood_type: str = Form(...),
        sex: str = Form(...),
        dob: date = Form(...),  # Pydantic/FastAPI handles date conversion
        subjects: str = Form(...),
        img: Union[UploadFile, str, None] = File(None)
):
    if not id:
        raise HTTPException(
            status_code=400,
            detail="Teacher ID is required for updating."
        )

    try:
        teacherId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid teacher UUID format: {str(e)}"
        )

    try:
        subject_ids = [
            uuid.UUID(s.strip())
            for s in subjects.split(',')
            if s.strip()
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subject UUID format: {str(e)}"
        )

    # Validate subjects list is not empty
    if not subject_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one subject must be assigned to the teacher."
        )

    try:
        sex_enum = UserSex(sex.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid sex value. Must be 'male' or 'female'."
        )

        # Validate phone format
    if not settings.PHONE_RE.match(phone.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid Indian phone number. Must be 10 digits starting with 6-9."
        )

    processed_img: Optional[UploadFile] = None
    if img is not None and not isinstance(img, str):
        # Check if it has the attributes of an UploadFile (duck typing)
        if hasattr(img, 'filename') and hasattr(img, 'file') and img.filename:
            processed_img = img
    elif isinstance(img, str) and img.strip():
        # If somehow a non-empty string is passed, treat as no image
        processed_img = None

    teacher_data = {
        "id": teacherId,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "address": address,
        "blood_type": blood_type,
        "sex": sex_enum,
        "dob": dob,
        "subjects": subject_ids
    }

    result = await TeacherUpdate(teacher_data, processed_img, session)
    return result


@router.delete("/delete", response_model=TeacherDeleteResponse)
def softDeleteTeacher(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Teacher ID is required for deleting."
        )

    result = teacherSoftDeleteWithLessonAndClassAndSubject(id, session)
    return result
