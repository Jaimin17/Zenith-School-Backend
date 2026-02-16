import uuid
from http.client import HTTPException

from fastapi import APIRouter
from fastapi.params import Form
from pyexpat.errors import messages

from deps import AdminUser
from core.database import SessionDep
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
def usersCount(current_user: AdminUser, session: SessionDep):
    admin_count = countAdmin(session)
    teacher_count = countTeacher(session)
    student_count = countStudent(session)
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
