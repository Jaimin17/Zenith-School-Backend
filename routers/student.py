import uuid
from datetime import date, datetime
from typing import List, Union, Optional

from fastapi import APIRouter, HTTPException, Form, UploadFile, File

from core.config import settings
from deps import CurrentUser, TeacherOrAdminUser, AdminUser, StudentOrTeacherOrAdminUser
from core.database import SessionDep
from models import UserSex
from schemas import StudentRead, SaveResponse, StudentSave, StudentUpdateBase, StudentDeleteResponse
from repository.student import getAllStudentsIsDeleteFalse, getAllStudentsOfTeacherAndIsDeleteFalse, countStudent, \
    countStudentBySexAll, getStudentByIdAndIsDeleteFalse, StudentUpdate, studentSoftDelete, \
    studentSaveWithImage

router = APIRouter(
    prefix="/student",
)


@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countStudent(session)


@router.get("/countStudentBySex")
def countStudentBySex(current_user: AdminUser, session: SessionDep):
    total = countStudentBySexAll(session)
    print(total)
    return total


@router.get("/get/{studentId}", response_model=StudentRead)
def getStudentById(studentId: uuid.UUID, current_user: StudentOrTeacherOrAdminUser, session: SessionDep):
    studentDetail = getStudentByIdAndIsDeleteFalse(studentId, session)
    return studentDetail


@router.get("/getAll", response_model=List[StudentRead])
def getAllStudents(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    user, role = current_user

    if role == "admin":
        all_students = getAllStudentsIsDeleteFalse(session, search, page)
    elif role == "teacher":
        all_students = getAllStudentsOfTeacherAndIsDeleteFalse(session, user.id, search, page)
    return all_students


@router.get("/{teacherId}", response_model=List[StudentRead])
def getStudentByTeacherId(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                          page: int = 1):
    all_students = getAllStudentsOfTeacherAndIsDeleteFalse(session, teacherId, search, page)
    return all_students


@router.post("/save", response_model=SaveResponse)
async def saveStudent(
        current_user: AdminUser,
        session: SessionDep,
        username: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        address: str = Form(...),
        blood_type: str = Form(...),
        sex: str = Form(...),
        dob: date = Form(...),
        parent_id: str = Form(...),
        class_id: str = Form(...),
        grade_id: str = Form(...),
        img: Union[UploadFile, str, None] = File(None)
):
    try:
        parent_uuid = uuid.UUID(parent_id.strip()) if parent_id else None
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parent UUID format: {str(e)}"
        )

    if not parent_uuid:
        raise HTTPException(
            status_code=400,
            detail="Parent ID is required."
        )

    try:
        class_uuid = uuid.UUID(class_id.strip()) if class_id else None
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid class UUID format: {str(e)}"
        )

    if not class_uuid:
        raise HTTPException(
            status_code=400,
            detail="Class ID is required."
        )

    try:
        grade_uuid = uuid.UUID(grade_id.strip()) if grade_id else None
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid grade UUID format: {str(e)}"
        )

    if not grade_uuid:
        raise HTTPException(
            status_code=400,
            detail="Grade ID is required."
        )

    try:
        sex_enum = UserSex(sex.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid sex value. Must be 'male' or 'female'."
        )

        # Validate phone format
    if not settings.PHONE_RE.match(phone.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid Indian phone number. Must be 10 digits starting with 6-9."
        )

    if not settings.EMAIL_RE.match(email.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format."
        )

    if not username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty.")

    if not first_name.strip():
        raise HTTPException(status_code=400, detail="First name cannot be empty.")

    if not last_name.strip():
        raise HTTPException(status_code=400, detail="Last name cannot be empty.")

    if not address.strip():
        raise HTTPException(status_code=400, detail="Address cannot be empty.")

    today = datetime.now().date()
    age = (today - dob).days // 365

    if age < 3 or age > 25:
        raise HTTPException(
            status_code=400,
            detail="Student age must be between 3 and 25 years."
        )

    processed_img: Optional[UploadFile] = None
    if img is not None and not isinstance(img, str):
        # Check if it has the attributes of an UploadFile (duck typing)
        if hasattr(img, 'filename') and hasattr(img, 'file') and img.filename:
            processed_img = img
    elif isinstance(img, str) and img.strip():
        # If somehow a non-empty string is passed, treat as no image
        processed_img = None

    student_data = {
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "address": address,
        "blood_type": blood_type,
        "sex": sex_enum,
        "dob": dob,
        "parent_id": parent_uuid,
        "class_id": class_uuid,
        "grade_id": grade_uuid
    }

    result = await studentSaveWithImage(student_data, processed_img, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateStudent(
        current_user: AdminUser, student: StudentUpdateBase, session: SessionDep
    ):
    if not student.id:
        raise HTTPException(
            status_code=400,
            detail="Student ID is required for updating."
        )

    if not student.username or len(student.username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not student.first_name or len(student.first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not student.last_name or len(student.last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not student.phone or len(student.phone.strip()) != 10:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be valid(10 Digits)."
        )

    if not student.address or len(student.address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    if not student.blood_type:
        raise HTTPException(
            status_code=400,
            detail="Blood type is required."
        )

    if not student.dob or not isinstance(student.dob, date):
        raise HTTPException(
            status_code=400,
            detail="Date of Birth is required."
        )

    if not isinstance(student.sex, UserSex):
        raise HTTPException(
            status_code=400,
            detail="Sex is required."
        )

    if not student.parent_id:
        raise HTTPException(
            status_code=400,
            detail="Parent is required."
        )

    if not student.class_id:
        raise HTTPException(
            status_code=400,
            detail="Assign student to a class."
        )

    if not student.grade_id:
        raise HTTPException(
            status_code=400,
            detail="Grade is required."
        )

    result = StudentUpdate(student, session)
    return result


@router.delete("/delete", response_model=StudentDeleteResponse)
def softDeleteStudent(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Student ID is required for deleting."
        )

    result = studentSoftDelete(id, session)
    return result
