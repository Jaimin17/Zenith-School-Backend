from fastapi import APIRouter
from deps import AdminUser
from core.database import SessionDep
from repository.admin import countAdmin
from repository.parent import countParent
from repository.student import countStudent
from repository.teacher import countTeacher
from schemas import UsersCount

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