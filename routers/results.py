import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, TeacherOrAdminUser
from repository.results import getAllResultsIsDeleteFalse, getAllResultsByTeacherIsDeleteFalse, \
    getAllResultsOfClassIsDeleteFalse, getAllResultsOfStudentIsDeleteFalse, getAllResultsOfParentIsDeleteFalse, \
    resultSave, resultUpdate, ResultSoftDelete
from schemas import ResultRead, SaveResponse, ResultSave, ResultUpdate, PaginatedResultResponse

router = APIRouter(
    prefix="/results",
)


@router.get("/getAll", response_model=PaginatedResultResponse)
def getAllResults(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_results = getAllResultsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_results = getAllResultsByTeacherIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_results = getAllResultsOfStudentIsDeleteFalse(user.id, session, search, page)
    elif role == "parent":
        all_results = getAllResultsOfParentIsDeleteFalse(user.id, session, search, page)
    return all_results


@router.get("/teacher/{teacherId}", response_model=List[ResultRead])
def getAllResultsByTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                           page: int = 1):
    all_results = getAllResultsByTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_results


@router.get("/class/{classId}", response_model=PaginatedResultResponse)
def getAllResultsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                         page: int = 1):
    all_results = getAllResultsOfClassIsDeleteFalse(classId, session, search, page)
    return all_results


@router.get("/student/{studentId}", response_model=List[ResultRead])
def getAllResultsOfStudent(studentId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                           page: int = 1):
    all_results = getAllResultsOfStudentIsDeleteFalse(studentId, session, search, page)
    return all_results


@router.post("/save", response_model=SaveResponse)
def saveResult(result: ResultSave, current_user: TeacherOrAdminUser, session: SessionDep):
    user, role = current_user

    if result.score is None or result.score < 0 or result.score > 650:
        raise HTTPException(
            status_code=400,
            detail="Score is not present. Should not be negative."
        )

    if result.exam_id is None and result.assignment_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either exam_id or assignment_id is required."
        )

    if result.exam_id is not None and result.assignment_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Only one of exam_id or assignment_id should be provided, not both."
        )

    if result.student_id is None or not isinstance(result.student_id, uuid.UUID):
        raise HTTPException(
            status_code=400,
            detail="student id is required."
        )

    result = resultSave(result, user.id, role, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateResult(current_user: TeacherOrAdminUser, result: ResultUpdate, session: SessionDep):
    user, role = current_user

    if not result.id:
        raise HTTPException(
            status_code=400,
            detail="Result ID is required for updating."
        )

    if result.score is None or result.score < 0 or result.score > 650:
        raise HTTPException(
            status_code=400,
            detail="Score is not present. Should not be negative."
        )

    if result.exam_id is None and result.assignment_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either exam_id or assignment_id is required."
        )

    if result.exam_id is not None and result.assignment_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Only one of exam_id or assignment_id should be provided, not both."
        )

    if result.student_id is None or not isinstance(result.student_id, uuid.UUID):
        raise HTTPException(
            status_code=400,
            detail="student id is required."
        )

    result = resultUpdate(result, user.id, role, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def softDeleteResult(current_user: TeacherOrAdminUser, id: uuid.UUID, session: SessionDep):
    user, role = current_user

    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Result ID is required for deleting."
        )

    result = ResultSoftDelete(id, user.id, role, session)
    return result

