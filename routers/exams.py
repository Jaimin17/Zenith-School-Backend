import uuid
from datetime import datetime, timezone
from typing import List

from fastapi.params import Form

from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, TeacherOrAdminUser
from repository.exams import getAllExamsIsDeleteFalse, getAllExamsOfTeacherIsDeleteFalse, \
    getAllExamsOfClassIsDeleteFalse, getAllExamsOfParentIsDeleteFalse, examSave, examUpdate, examSoftDelete, \
    getAllExamsOfStudentIsDeleteFalse, getFullListOfExamsOfClassIsDeleteFalse
from schemas import ExamRead, SaveResponse, ExamSave, ExamUpdate, ExamDeleteResponse, PaginatedExamResponse

router = APIRouter(
    prefix="/exam",
)


@router.get("/getAll", response_model=PaginatedExamResponse)
def getAllExam(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_exams = getAllExamsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_exams = getAllExamsOfTeacherIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_exams = getAllExamsOfClassIsDeleteFalse(user.class_id, session, search, page)
    else:
        all_exams = getAllExamsOfParentIsDeleteFalse(user.id, session, search, page)
    return all_exams


@router.get("/teacher/{teacherId}", response_model=PaginatedExamResponse)
def getAllExamsOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                         page: int = 1):
    all_exams = getAllExamsOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_exams


@router.get("/class/{classId}", response_model=PaginatedExamResponse)
def getAllExamsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                       page: int = 1):
    all_exams = getAllExamsOfClassIsDeleteFalse(classId, session, search, page)
    return all_exams


@router.get("/allOfClass/{classId}", response_model=List[ExamRead])
def getFullListOfExamsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    all_exams = getFullListOfExamsOfClassIsDeleteFalse(classId, session)
    return all_exams


@router.get("/student/{studentId}", response_model=PaginatedExamResponse)
def getAllExamsOfStudent(studentId: uuid.UUID, current_user: AllUser, session: SessionDep, search: str = None,
                         page: int = 1):
    all_exams = getAllExamsOfStudentIsDeleteFalse(studentId, session, search, page)
    return all_exams


@router.post("/save", response_model=SaveResponse)
def saveExam(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        title: str = Form(...),
        start_time: datetime = Form(...),
        end_time: datetime = Form(...),
        lesson_id: str = Form(...)
):
    user, role = current_user

    if not title or len(title.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Title is required and must be at least 2 characters long."
        )

    exam_start = start_time
    if exam_start.tzinfo is None:
        exam_start = exam_start.replace(tzinfo=timezone.utc)

    if not start_time or not isinstance(start_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not end_time or not isinstance(end_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="Exam start time must be before end time."
        )

    if exam_start < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Exam start time cannot be in the past."
        )

    if not lesson_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson id is required."
        )
    else:
        try:
            lessionId: uuid.UUID = uuid.UUID(lesson_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Lesson id is not valid uuid."
            )

    exam_data: ExamSave = ExamSave(
        title=title,
        start_time=start_time,
        end_time=end_time,
        lesson_id=lessionId
    )

    result = examSave(exam_data, user.id, role, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateExam(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        start_time: datetime = Form(...),
        end_time: datetime = Form(...),
        lesson_id: str = Form(...)
):
    user, role = current_user

    exam_start = start_time
    if exam_start.tzinfo is None:
        exam_start = exam_start.replace(tzinfo=timezone.utc)

    if not id:
        raise HTTPException(
            status_code=400,
            detail="Exam ID is required for updating."
        )
    else:
        try:
            exam_id: uuid.UUID = uuid.UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Exam ID is not valid uuid."
            )

    if not title or len(title.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Title is required and must be at least 2 characters long."
        )

    if not start_time or not isinstance(start_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not end_time or not isinstance(end_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="Exam start time must be before end time."
        )

    if exam_start < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Exam start time cannot be in the past."
        )

    if not lesson_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson id is required."
        )
    else:
        try:
            lessionId: uuid.UUID = uuid.UUID(lesson_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Lesson id is not valid uuid."
            )

    exam_data: ExamUpdate = ExamUpdate(
        id=exam_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        lesson_id=lessionId
    )

    result = examUpdate(exam_data, user.id, role, session)
    return result


@router.delete("/delete", response_model=ExamDeleteResponse)
def softDeleteExam(current_user: TeacherOrAdminUser, id: uuid.UUID, session: SessionDep):
    result = examSoftDelete(id, session)
    return result
