import uuid
from datetime import timezone, date
from typing import List, Union, Optional
from core.database import SessionDep
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from deps import CurrentUser, AllUser, TeacherOrAdminUser
from repository.assignments import getAllAssignmentsIsDeleteFalse, getAllAssignmentsOfTeacherIsDeleteFalse, \
    getAllAssignmentsOfClassIsDeleteFalse, getAllAssignmentsOfParentIsDeleteFalse, assignmentSaveWithPdf, \
    assignmentUpdate, \
    assignmentSoftDelete
from schemas import AssignmentRead, SaveResponse, AssignmentSave, AssignmentUpdate, AssignmentDeleteResponse

router = APIRouter(
    prefix="/assignments",
)


@router.get("/getAll", response_model=List[AssignmentRead])
def getAllExam(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user
    if role == "admin":
        all_exams = getAllAssignmentsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_exams = getAllAssignmentsOfTeacherIsDeleteFalse(user.id, session, search, page)
    elif role == "student":
        all_exams = getAllAssignmentsOfClassIsDeleteFalse(user.class_id, session, search, page)
    else:
        all_exams = getAllAssignmentsOfParentIsDeleteFalse(user.id, session, search, page)

    return all_exams


@router.get("/teacher/{teacherId}", response_model=List[AssignmentRead])
def getAllExamsOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                         page: int = 1):
    all_exams = getAllAssignmentsOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_exams


@router.get("/class/{classId}", response_model=List[AssignmentRead])
def getAllExamsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                       page: int = 1):
    all_exams = getAllAssignmentsOfClassIsDeleteFalse(classId, session, search, page)
    return all_exams


@router.post("/save", response_model=SaveResponse)
async def saveAssignments(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        title: str = Form(...),
        start_date: date = Form(...),
        end_date: date = Form(...),
        lesson_id: str = Form(...),
        pdf: Union[UploadFile, str, None] = File(None)
):
    user, role = current_user

    if not title or len(title.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Title is required and must be at least 2 characters long."
        )

    if not start_date or not isinstance(start_date, date):
        raise HTTPException(
            status_code=400,
            detail="Start date is required."
        )

    if not end_date or not isinstance(end_date, date):
        raise HTTPException(
            status_code=400,
            detail="End date is required."
        )

    if start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="Assignment start date must be before end date."
        )

    if start_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Assignment start date cannot be in the past."
        )

    if not lesson_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson id is required."
        )

    try:
        lesson_uuid = uuid.UUID(lesson_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Lesson UUID format: {str(e)}"
        )

    processed_pdf: Optional[UploadFile] = None
    if pdf is not None and not isinstance(pdf, str):
        if hasattr(pdf, 'filename') and hasattr(pdf, 'file') and pdf.filename:
            processed_pdf = pdf

    assignment = AssignmentSave(
        title=title.strip(),
        start_date=start_date,
        end_date=end_date,
        lesson_id=lesson_uuid
    )

    result = await assignmentSaveWithPdf(assignment, processed_pdf, user.id, role, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateAssignment(current_user: TeacherOrAdminUser, assignment: AssignmentUpdate, session: SessionDep):
    user, role = current_user

    if not assignment.id:
        raise HTTPException(
            status_code=400,
            detail="Assignment ID is required for updating."
        )

    if not assignment.title or len(assignment.title.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Title is required and must be at least 2 characters long."
        )

    if not assignment.start_date or not isinstance(assignment.start_date, date):
        raise HTTPException(
            status_code=400,
            detail="Start date is required."
        )

    if not assignment.end_date or not isinstance(assignment.end_date, date):
        raise HTTPException(
            status_code=400,
            detail="End date is required."
        )

    if assignment.start_date >= assignment.end_date:
        raise HTTPException(
            status_code=400,
            detail="Assignment start date must be before end date."
        )

    if assignment.start_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Assignment start date cannot be in the past."
        )

    if not assignment.lesson_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson id is required."
        )

    result = assignmentUpdate(assignment, user.id, role, session)
    return result


@router.delete("/delete", response_model=AssignmentDeleteResponse)
def softDeleteAssignment(current_user: TeacherOrAdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Assignment ID is required for deleting."
        )

    result = assignmentSoftDelete(id, session)
    return result
