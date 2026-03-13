import uuid
from http.client import HTTPException
from typing import Optional

from fastapi import APIRouter
from fastapi.params import Form
from pyexpat.errors import messages
from sqlalchemy import func
from sqlmodel import select

from deps import AdminUser
from core.database import SessionDep
from models import StudentClassHistory, Student as StudentModel, UserSex
from repository.admin import countAdmin, updateAdminPassword
from repository.parent import countParent
from repository.student import countStudent
from repository.teacher import countTeacher
from schemas import UsersCount, updatePasswordModel

router = APIRouter(
    prefix="/admin",
)


@router.get("/count", response_model=int)
def count(current_user: AdminUser, session: SessionDep):
    return countAdmin(session)


@router.get("/allUsersCount", response_model=UsersCount)
def usersCount(current_user: AdminUser, session: SessionDep, year_id: Optional[uuid.UUID] = None):
    admin_count = countAdmin(session)
    if year_id:
        boys_count = session.exec(
            select(func.count(StudentClassHistory.student_id.distinct()))
            .join(StudentModel, StudentModel.id == StudentClassHistory.student_id)
            .where(
                StudentClassHistory.academic_year_id == year_id,
                StudentModel.is_delete == False,
                StudentModel.sex == UserSex.MALE,
            )
        ).one()
        girls_count = session.exec(
            select(func.count(StudentClassHistory.student_id.distinct()))
            .join(StudentModel, StudentModel.id == StudentClassHistory.student_id)
            .where(
                StudentClassHistory.academic_year_id == year_id,
                StudentModel.is_delete == False,
                StudentModel.sex == UserSex.FEMALE,
            )
        ).one()
        student_count = {"boys": boys_count, "girls": girls_count}
        teacher_count = countTeacher(session)
        parent_count = session.exec(
            select(func.count(StudentModel.parent_id.distinct()))
            .join(StudentClassHistory, StudentClassHistory.student_id == StudentModel.id)
            .where(
                StudentClassHistory.academic_year_id == year_id,
                StudentModel.is_delete == False,
                StudentModel.parent_id != None,
            )
        ).one()
    else:
        student_count = countStudent(session)
        teacher_count = countTeacher(session)
        parent_count = countParent(session)

    return UsersCount(
        admins=admin_count,
        teachers=teacher_count,
        students=student_count,
        parents=parent_count
    )


@router.put("/updatePassword/{admin_id}", response_model=str)
def updatePassword(
        current_user: AdminUser,
        session: SessionDep,
        admin_id: str,
        updated_password: str = Form(...),
):
    if not admin_id:
        raise HTTPException(
            status_code=404,
            detail="Admin Id is not present."
        )
    else:
        try:
            adminId = uuid.UUID(admin_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Admin Id is not a valid type."
            )

    if not updated_password or len(updated_password.strip()) < 8:
        raise HTTPException(
            status_code=400,
            detail="New password is not present or is less then 8 char."
        )

    data: updatePasswordModel = updatePasswordModel(
        id=adminId,
        updated_password=updated_password.strip(),
    )

    return updateAdminPassword(data, session)
