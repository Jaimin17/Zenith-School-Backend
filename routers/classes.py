import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, TeacherOrAdminUser, AdminUser, StudentUser
from repository.classes import getAllClassesIsDeleteFalse, getAllClassOfTeacherAndIsDeleteFalse, findClassById, \
    classSave, ClassUpdate, ClassSoftDeleteWithLessonsStudentsEventsAnnoucements, countAllClassOfTheTeacher, \
    getClassOfStudentAndIsDeleteFalse, getAllClassesIsDeleteFalseAtOnce
from schemas import ClassRead, SaveResponse, ClassSave, ClassUpdateBase, ClassDeleteResponse, PaginatedClassResponse

router = APIRouter(
    prefix="/classes",
)


@router.get("/getAll", response_model=PaginatedClassResponse)
def getAllClasses(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_classes = getAllClassesIsDeleteFalse(session, search, page)
    else:
        all_classes = getAllClassOfTeacherAndIsDeleteFalse(user.id, session, search, page)
    return all_classes


@router.get("/getFullList", response_model=List[ClassRead])
def getAllClassesAtOnce(current_user: AdminUser, session: SessionDep):
    all_classes = getAllClassesIsDeleteFalseAtOnce(session)
    return all_classes


@router.get("/getStudentClass", response_model=ClassRead)
def getStudentClass(current_user: StudentUser, session: SessionDep):
    user, role = current_user
    student_class = getClassOfStudentAndIsDeleteFalse(user.id, session)
    return student_class


@router.get("/countByTeacher/{teacherId}", response_model=int)
def countClassByTeacher(current_user: TeacherOrAdminUser, teacherId: uuid.UUID, session: SessionDep):
    total_class = countAllClassOfTheTeacher(teacherId, session)
    return total_class


@router.get("/{supervisorId}", response_model=PaginatedClassResponse)
def getClassesOfTeacher(supervisorId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                        page: int = 1):
    teacher_class = getAllClassOfTeacherAndIsDeleteFalse(supervisorId, session, search, page)
    return teacher_class


@router.get("/get/{classId}", response_model=ClassRead)
def getClassById(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    if classId is None:
        raise HTTPException(status_code=400, detail="Class ID is not present.")

    result = findClassById(classId, session)
    return result


@router.post("/save", response_model=SaveResponse)
def saveClass(current_user: AdminUser, classes: ClassSave, session: SessionDep):
    if not classes.name or len(classes.name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Class name is required and must contain at least 1 character."
        )

    if classes.capacity is None or classes.capacity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Capacity is required and must be greater than 0."
        )

    if classes.gradeId is None:
        raise HTTPException(
            status_code=400,
            detail="gradeId is required."
        )

    result = classSave(classes, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateClass(current_user: AdminUser, classes: ClassUpdateBase, session: SessionDep):
    if not classes.id:
        raise HTTPException(
            status_code=400,
            detail="Class ID is required for updating."
        )

    if not classes.name or len(classes.name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Class name is required and must contain at least 1 character."
        )

    if classes.capacity is None or classes.capacity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Capacity is required and must be greater than 0."
        )

    if classes.gradeId is None:
        raise HTTPException(
            status_code=400,
            detail="gradeId is required."
        )

    result = ClassUpdate(classes, session)
    return result


@router.delete("/delete", response_model=ClassDeleteResponse)
def softDeleteClass(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Class ID is required for deleting."
        )

    result = ClassSoftDeleteWithLessonsStudentsEventsAnnoucements(id, session)
    return result
