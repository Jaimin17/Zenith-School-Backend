import uuid
from typing import List, Optional

from fastapi.params import Form

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
def getAllResults(
        current_user: AllUser,
        session: SessionDep,
        search: str = None,
        page: int = 1,
        class_id: str = None,  # New
        exam_id: str = None,  # New
        assignment_id: str = None,  # New
        type: str = None  # "exam" or "assignment"  # New
):
    user, role = current_user
    if role == "admin":
        all_results = getAllResultsIsDeleteFalse(session, search, page, class_id, exam_id, assignment_id, type)
    elif role == "teacher":
        all_results = getAllResultsByTeacherIsDeleteFalse(user.id, session, search, page, class_id, exam_id,
                                                          assignment_id, type)
    elif role == "student":
        all_results = getAllResultsOfStudentIsDeleteFalse(user.id, session, search, page, class_id, exam_id,
                                                          assignment_id, type)
    elif role == "parent":
        all_results = getAllResultsOfParentIsDeleteFalse(user.id, session, search, page, class_id, exam_id,
                                                         assignment_id, type)
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


@router.get("/student/{studentId}", response_model=PaginatedResultResponse)
def getAllResultsOfStudent(
        studentId: uuid.UUID,
        current_user: CurrentUser,
        session: SessionDep,
        search: str = None,
        page: int = 1,
        class_id: str = None,  # New
        exam_id: str = None,  # New
        assignment_id: str = None,  # New
        type: str = None  # "exam" or "assignment"  # New
):
    all_results = getAllResultsOfStudentIsDeleteFalse(studentId, session, search, page, class_id, exam_id,
                                                      assignment_id, type)
    return all_results


@router.post("/save", response_model=SaveResponse)
def saveResult(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        score: float = Form(...),
        exam_id: Optional[str] = Form(None),
        assignment_id: Optional[str] = Form(None),
        student_id: str = Form(...),
):
    user, role = current_user

    if score is None or score < 0 or score > 100:
        raise HTTPException(
            status_code=400,
            detail="Score is not present. Should not be negative."
        )

    examId = None
    assignmentId = None

    if exam_id is None and assignment_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either exam_id or assignment_id is required."
        )

    if exam_id is not None and assignment_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Only one of exam_id or assignment_id should be provided, not both."
        )

    if exam_id is not None:
        try:
            examId = uuid.UUID(exam_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Exam Id is not a valid type."
            )

    if assignment_id is not None:
        try:
            assignmentId = uuid.UUID(assignment_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Assignment Id is not a valid type."
            )

    if student_id is None:
        raise HTTPException(
            status_code=400,
            detail="student id is required."
        )
    else:
        try:
            studentId = uuid.UUID(student_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Student Id is not a valid type."
            )

    result_data: ResultSave = ResultSave(
        score=score,
        exam_id=examId,
        assignment_id=assignmentId,
        student_id=studentId,
    )

    result = resultSave(result_data, user.id, role, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateResult(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        id: str = Form(...),
        score: float = Form(...),
        exam_id: Optional[str] = Form(None),
        assignment_id: Optional[str] = Form(None),
        student_id: str = Form(...),
):
    user, role = current_user

    if not id:
        raise HTTPException(
            status_code=400,
            detail="Result ID is required for updating."
        )
    else:
        try:
            ID = uuid.UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Result Id is not a valid type."
            )

    if score is None or score < 0 or score > 100:
        raise HTTPException(
            status_code=400,
            detail="Score is not present. Should not be negative."
        )

    examId = None
    assignmentId = None

    if exam_id is None and assignment_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either exam_id or assignment_id is required."
        )

    if exam_id is not None and assignment_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Only one of exam_id or assignment_id should be provided, not both."
        )

    if exam_id is not None:
        try:
            examId = uuid.UUID(exam_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Exam Id is not a valid type."
            )

    if assignment_id is not None:
        try:
            assignmentId = uuid.UUID(assignment_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Assignment Id is not a valid type."
            )

    if student_id is None:
        raise HTTPException(
            status_code=400,
            detail="student id is required."
        )
    else:
        try:
            studentId = uuid.UUID(student_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Student Id is not a valid type."
            )

    result_data: ResultUpdate = ResultUpdate(
        id=ID,
        score=score,
        exam_id=examId,
        assignment_id=assignmentId,
        student_id=studentId,
    )

    result = resultUpdate(result_data, user.id, role, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def softDeleteResult(current_user: TeacherOrAdminUser, id: uuid.UUID, session: SessionDep):
    user, role = current_user

    result = ResultSoftDelete(id, user.id, role, session)
    return result
