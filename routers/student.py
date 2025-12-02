import uuid
from typing import List

from fastapi import APIRouter
from deps import CurrentUser, TeacherOrAdminUser, AdminUser, StudentOrTeacherOrAdminUser
from core.database import SessionDep
from schemas import StudentRead
from repository.student import getAllStudentsIsDeleteFalse, getAllStudentsOfTeacherAndIsDeleteFalse, countStudent, \
    countStudentBySexAll, getStudentByIdAndIsDeleteFalse

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
