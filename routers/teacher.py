import uuid
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Form, UploadFile, File, Depends

from core.config import settings
from deps import CurrentUser, TeacherOrAdminUser, AdminUser
from core.database import SessionDep
from models import UserSex
from repository.teacher import getAllTeachersIsDeleteFalse, getAllTeachersOfClassAndIsDeleteFalse, countTeacher, \
    findTeacherById, TeacherUpdate, teacherSoftDeleteWithLessonAndClassAndSubject, teacherSaveWithImage
from schemas import TeacherRead, SaveResponse, TeacherSave, TeacherUpdateBase, TeacherDeleteResponse

router = APIRouter(
    prefix="/teacher",
)


@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countTeacher(session)


@router.get("/getAll", response_model=List[TeacherRead])
def getAllTeachers(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    all_teachers = getAllTeachersIsDeleteFalse(session, search, page)
    return all_teachers


@router.get("/{classId}", response_model=List[TeacherRead])
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
        img: Optional[UploadFile] = File(None)
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

    result = await teacherSaveWithImage(teacher_data, img, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateTeacher(current_user: AdminUser, teacher: TeacherUpdateBase, session: SessionDep):
    if not teacher.id:
        raise HTTPException(
            status_code=400,
            detail="Teacher ID is required for updating."
        )

    if not teacher.username or len(teacher.username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not teacher.first_name or len(teacher.first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not teacher.last_name or len(teacher.last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not teacher.phone or len(teacher.phone.strip()) != 10:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be valid(10 Digits)."
        )

    if not teacher.address or len(teacher.address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    if not teacher.blood_type:
        raise HTTPException(
            status_code=400,
            detail="Blood type is required."
        )

    if not teacher.dob or not isinstance(teacher.dob, date):
        raise HTTPException(
            status_code=400,
            detail="Date of Birth is required."
        )

    if not isinstance(teacher.sex, UserSex):
        raise HTTPException(
            status_code=400,
            detail="Sex is required."
        )

    if not teacher.subjects or len(teacher.subjects) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one subject must be assigned to the teacher."
        )

    result = TeacherUpdate(teacher, session)
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
