import uuid
from datetime import timezone, date
from typing import List, Union, Optional
from core.database import SessionDep
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from deps import CurrentUser, AllUser, TeacherOrAdminUser
from models import Assignment
from repository.assignments import getAllAssignmentsIsDeleteFalse, getAllAssignmentsOfTeacherIsDeleteFalse, \
    getAllAssignmentsOfClassIsDeleteFalse, getAllAssignmentsOfParentIsDeleteFalse, assignmentSaveWithPdf, \
    assignmentUpdate, \
    assignmentSoftDelete, getAssignmentById
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


@router.get("/getById/{assignmentId}", response_model=AssignmentRead)
def getById(current_user: AllUser, session: SessionDep, assignmentId: uuid.UUID):
    user, role = current_user

    assignment_detail: Optional[Assignment] = getAssignmentById(session, assignmentId)

    if not assignment_detail:
        raise HTTPException(
            status_code=404,
            detail="Assignment not found with provided ID."
        )

    # Authorization checks based on role
    if role.lower() == "admin":
        return assignment_detail

    elif role.lower() == "teacher":
        # Check if the assignment's lesson belongs to this teacher
        if assignment_detail.lesson.teacher_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this assignment."
            )
        return assignment_detail

    elif role.lower() == "student":
        # Check if the student belongs to the class of this assignment's lesson
        if assignment_detail.lesson.class_id:
            class_students = [s.id for s in assignment_detail.lesson.related_class.students if not s.is_delete]
            if user.id not in class_students:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to access this assignment."
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="This assignment is not associated with any class."
            )
        return assignment_detail

    elif role.lower() == "parent":
        # Check if any of the parent's children are in the class
        if not user.students:
            raise HTTPException(
                status_code=403,
                detail="No students associated with your account."
            )

        if assignment_detail.lesson.class_id:
            class_student_ids = [s.id for s in assignment_detail.lesson.related_class.students if not s.is_delete]
            parent_student_ids = [s.id for s in user.students if not s.is_delete]

            # Check if any of parent's students are in the class
            has_access = any(student_id in class_student_ids for student_id in parent_student_ids)

            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="None of your children have access to this assignment."
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="This assignment is not associated with any class."
            )
        return assignment_detail

    else:
        raise HTTPException(
            status_code=403,
            detail="Invalid user role."
        )


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
        pdf: Union[UploadFile, str] = File(...)
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
    if pdf is None or isinstance(pdf, str):
        raise HTTPException(
            status_code=400,
            detail="PDF file is required for assignment creation."
        )

    if not hasattr(pdf, 'filename') or not hasattr(pdf, 'file') or not pdf.filename:
        raise HTTPException(
            status_code=400,
            detail="PDF file is required for assignment creation."
        )

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
async def updateAssignment(
        current_user: TeacherOrAdminUser,
        session: SessionDep,
        id: str = Form(...),
        title: str = Form(...),
        start_date: date = Form(...),
        end_date: date = Form(...),
        lesson_id: str = Form(...),
        pdf: Union[UploadFile, str, None] = File(None)
):
    user, role = current_user

    if not id:
        raise HTTPException(
            status_code=400,
            detail="Assignment ID is required for updating."
        )

    try:
        assignmentId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid assignment UUID format: {str(e)}"
        )

    if not assignmentId:
        raise HTTPException(
            status_code=400,
            detail="Assignment ID is required for updating."
        )

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
    elif isinstance(pdf, str) and pdf.strip():
        processed_pdf = None

    assignment = AssignmentUpdate(
        id=assignmentId,
        title=title.strip(),
        start_date=start_date,
        end_date=end_date,
        lesson_id=lesson_uuid
    )

    result = await assignmentUpdate(assignment, processed_pdf, user.id, role, session)
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
