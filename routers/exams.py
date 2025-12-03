import uuid
from datetime import datetime, timezone
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, TeacherOrAdminUser
from repository.exams import getAllExamsIsDeleteFalse, getAllExamsOfTeacherIsDeleteFalse, \
    getAllExamsOfClassIsDeleteFalse, getAllExamsOfParentIsDeleteFalse, examSave, examUpdate, examSoftDelete
from schemas import ExamRead, SaveResponse, ExamSave, ExamUpdate, ExamDeleteResponse

router = APIRouter(
    prefix="/exam",
)


@router.get("/getAll", response_model=List[ExamRead])
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


@router.get("/teacher/{teacherId}", response_model=List[ExamRead])
def getAllExamsOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                         page: int = 1):
    all_exams = getAllExamsOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_exams


@router.get("/class/{classId}", response_model=List[ExamRead])
def getAllExamsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                       page: int = 1):
    all_exams = getAllExamsOfClassIsDeleteFalse(classId, session, search, page)
    return all_exams


@router.post("/save", response_model=SaveResponse)
def saveExam(exam: ExamSave, current_user: TeacherOrAdminUser, session: SessionDep):
    user, role = current_user

    if not exam.title or len(exam.title.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Title is required and must be at least 2 characters long."
        )

    exam_start = exam.start_time
    if exam_start.tzinfo is None:
        exam_start = exam_start.replace(tzinfo=timezone.utc)

    if not exam.start_time or not isinstance(exam.start_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not exam.end_time or not isinstance(exam.end_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if exam.start_time >= exam.end_time:
        raise HTTPException(
            status_code=400,
            detail="Exam start time must be before end time."
        )

    if exam_start < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Exam start time cannot be in the past."
        )

    if not exam.lesson_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson id is required."
        )

    result = examSave(exam, user.id, role, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateExam(current_user: TeacherOrAdminUser, exam: ExamUpdate, session: SessionDep):
    user, role = current_user

    exam_start = exam.start_time
    if exam_start.tzinfo is None:
        exam_start = exam_start.replace(tzinfo=timezone.utc)

    if not exam.id:
        raise HTTPException(
            status_code=400,
            detail="Exam ID is required for updating."
        )

    if not exam.title or len(exam.title.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Title is required and must be at least 2 characters long."
        )

    if not exam.start_time or not isinstance(exam.start_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    if not exam.end_time or not isinstance(exam.end_time, datetime):
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    if exam.start_time >= exam.end_time:
        raise HTTPException(
            status_code=400,
            detail="Exam start time must be before end time."
        )

    if exam_start < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Exam start time cannot be in the past."
        )

    if not exam.lesson_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson id is required."
        )

    result = examUpdate(exam, user.id, role, session)
    return result


@router.delete("/delete", response_model=ExamDeleteResponse)
def softDeleteExam(current_user: TeacherOrAdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Exam ID is required for deleting."
        )

    result = examSoftDelete(id, session)
    return result
