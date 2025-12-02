import uuid
from datetime import date
from typing import List

from fastapi import APIRouter, HTTPException
from deps import CurrentUser, TeacherOrAdminUser, AdminUser, StudentOrTeacherOrAdminUser
from core.database import SessionDep
from models import UserSex
from schemas import StudentRead, SaveResponse, StudentSave, StudentUpdateBase
from repository.student import getAllStudentsIsDeleteFalse, getAllStudentsOfTeacherAndIsDeleteFalse, countStudent, \
    countStudentBySexAll, getStudentByIdAndIsDeleteFalse, studentSave, StudentUpdate, studentSoftDelete

router = APIRouter(
    prefix="/student",
)


@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countStudent(session)


@router.get("/countStudentBySex")
def countStudentBySex(current_user: AdminUser, session: SessionDep):
    total = countStudentBySexAll(session)
    print(total)
    return total


@router.get("/get/{studentId}", response_model=StudentRead)
def getStudentById(studentId: uuid.UUID, current_user: StudentOrTeacherOrAdminUser, session: SessionDep):
    studentDetail = getStudentByIdAndIsDeleteFalse(studentId, session)
    return studentDetail


@router.get("/getAll", response_model=List[StudentRead])
def getAllStudents(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user

    if role == "admin":
        all_students = getAllStudentsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_students = getAllStudentsOfTeacherAndIsDeleteFalse(session, user.id, search, page)
    return all_students


@router.get("/{teacherId}", response_model=List[StudentRead])
def getStudentByTeacherId(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                          page: int = 1):
    all_students = getAllStudentsOfTeacherAndIsDeleteFalse(session, teacherId, search, page)
    return all_students


@router.post("/save", response_model=SaveResponse)
def saveStudent(student: StudentSave, current_user: AdminUser, session: SessionDep):
    if not student.username or len(student.username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not student.first_name or len(student.first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not student.last_name or len(student.last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not student.phone or len(student.phone.strip()) != 10:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be valid(10 Digits)."
        )

    if not student.address or len(student.address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    if not student.blood_type:
        raise HTTPException(
            status_code=400,
            detail="Blood type is required."
        )

    if not student.dob or not isinstance(student.dob, date):
        raise HTTPException(
            status_code=400,
            detail="Date of Birth is required."
        )

    if not isinstance(student.sex, UserSex):
        raise HTTPException(
            status_code=400,
            detail="Sex is required."
        )

    if not student.parent_id:
        raise HTTPException(
            status_code=400,
            detail="Parent is required."
        )

    if not student.class_id:
        raise HTTPException(
            status_code=400,
            detail="Assign student to a class."
        )

    if not student.grade_id:
        raise HTTPException(
            status_code=400,
            detail="Grade is required."
        )

    result = studentSave(student, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateStudent(current_user: AdminUser, student: StudentUpdateBase, session: SessionDep):
    if not student.id:
        raise HTTPException(
            status_code=400,
            detail="Student ID is required for updating."
        )

    if not student.username or len(student.username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not student.first_name or len(student.first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not student.last_name or len(student.last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not student.phone or len(student.phone.strip()) != 10:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be valid(10 Digits)."
        )

    if not student.address or len(student.address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    if not student.blood_type:
        raise HTTPException(
            status_code=400,
            detail="Blood type is required."
        )

    if not student.dob or not isinstance(student.dob, date):
        raise HTTPException(
            status_code=400,
            detail="Date of Birth is required."
        )

    if not isinstance(student.sex, UserSex):
        raise HTTPException(
            status_code=400,
            detail="Sex is required."
        )

    if not student.parent_id:
        raise HTTPException(
            status_code=400,
            detail="Parent is required."
        )

    if not student.class_id:
        raise HTTPException(
            status_code=400,
            detail="Assign student to a class."
        )

    if not student.grade_id:
        raise HTTPException(
            status_code=400,
            detail="Grade is required."
        )

    result = StudentUpdate(student, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def softDeleteStudent(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Student ID is required for deleting."
        )

    result = studentSoftDelete(id, session)
    return result
