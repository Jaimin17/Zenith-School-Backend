import uuid
from datetime import date
from typing import List

from fastapi import APIRouter, HTTPException
from deps import CurrentUser, TeacherOrAdminUser, AdminUser
from core.database import SessionDep
from models import UserSex
from repository.teacher import getAllTeachersIsDeleteFalse, getAllTeachersOfClassAndIsDeleteFalse, countTeacher, \
    findTeacherById, teacherSave, TeacherUpdate, teacherSoftDeleteWithLessonAndClassAndSubject
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
def saveTeacher(teacher: TeacherSave, current_user: AdminUser, session: SessionDep):
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

    result = teacherSave(teacher, session)
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
