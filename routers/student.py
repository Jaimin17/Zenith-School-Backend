import uuid
from datetime import date, datetime
from typing import List, Union, Optional

from fastapi import APIRouter, HTTPException, Form, UploadFile, File

from core.config import settings
from deps import CurrentUser, StudentOrAdminUser, AdminUser, StudentOrTeacherOrAdminUser, ParentOrTeacherOrAdminUser, \
    UserRole, ParentUser, StudentOrParentOrAdminUser
from core.database import SessionDep
from models import UserSex
from schemas import StudentRead, SaveResponse, StudentSave, StudentUpdateBase, StudentDeleteResponse, \
    PaginatedStudentResponse, updatePasswordModel, ChildItem, BulkPromoteRequest, BulkPromoteResponse, \
    AssignClassRequest, StudentYearDataResponse, StudentHistoryResponse
from repository.student import getAllStudentsIsDeleteFalse, getAllStudentsOfTeacherAndIsDeleteFalse, countStudent, \
    countStudentBySexAll, getStudentByIdAndIsDeleteFalse, StudentUpdate, studentSoftDelete, \
    studentSaveWithImage, getAllStudentsOfParentAndIsDeleteFalse, getAllStudentsOfClassAndIsDeleteFalse, \
    updateStudentPassword, getChildrenOfParentLightweight, bulkPromoteStudents, assignClassToStudent
from repository.academicYear import getAcademicYearById, getActiveAcademicYear
from repository.studentClassHistory import getStudentFullHistory, getHistoricalLessons
from repository.attendance import getStudentAttendanceByDateRange, getStudentYearAttendanceSummary
from repository.results import getStudentResultsByDateRange

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


@router.get("/getAll", response_model=PaginatedStudentResponse)
def getAllStudents(
    current_user: ParentOrTeacherOrAdminUser,
    session: SessionDep,
    search: str = None,
    page: int = 1,
    year_id: Optional[uuid.UUID] = None,
):
    user, role = current_user

    if role == "admin":
        all_students = getAllStudentsIsDeleteFalse(session, search, page, year_id)
    elif role == "teacher":
        all_students = getAllStudentsOfTeacherAndIsDeleteFalse(session, user.id, search, page, year_id)
    else:
        all_students = getAllStudentsOfParentAndIsDeleteFalse(session, user.id, search, page, year_id)
    return all_students


@router.get("/byTeacher/{teacherId}", response_model=PaginatedStudentResponse)
async def getStudentByTeacherId(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep,
                                search: str = None,
                                page: int = 1):
    all_students = await getAllStudentsOfTeacherAndIsDeleteFalse(session, teacherId, search, page)
    return all_students


@router.get("/getStudentsOfClass/{classId}", response_model=List[StudentRead])
async def getStudentsOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    all_students = await getAllStudentsOfClassAndIsDeleteFalse(classId, session)
    return all_students


@router.post("/save", response_model=SaveResponse)
async def saveStudent(
        current_user: AdminUser,
        session: SessionDep,
        username: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
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

    if not password.strip() or len(password.strip()) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password is Required. And should be at least 6 characters long."
        )

    if not settings.BLOOD_TYPE_RE.match(blood_type.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid blood type."
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

    if not blood_type.strip():
        raise HTTPException(status_code=400, detail="Blood type cannot be empty.")

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
        "grade_id": grade_uuid,
        "password": password,
    }

    result = await studentSaveWithImage(student_data, processed_img, session)
    return result


@router.put("/updatePassword/{student_id}", response_model=str)
def updatePassword(
        current_user: StudentOrAdminUser,
        session: SessionDep,
        student_id: str,
        updated_password: str = Form(...),
):
    user, role = current_user

    if not student_id:
        raise HTTPException(
            status_code=404,
            detail="Student Id is not present."
        )
    else:
        try:
            studentId = uuid.UUID(student_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Student Id is not a valid type."
            )

    if role == UserRole.STUDENT and user.id != student_id:
        raise HTTPException(
            status_code=401,
            detail="Not enough permissions to update the password."
        )

    if not updated_password or len(updated_password.strip()) < 8:
        raise HTTPException(
            status_code=400,
            detail="New password is not present or is less then 8 char."
        )

    data: updatePasswordModel = updatePasswordModel(
        id=studentId,
        updated_password=updated_password.strip(),
    )

    return updateStudentPassword(data, session)


@router.put("/update", response_model=SaveResponse)
async def updateStudent(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
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
        studentId = uuid.UUID(id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid student UUID format: {str(e)}"
        )

    try:
        parent_uuid = uuid.UUID(parent_id.strip()) if parent_id and parent_id.strip() else None
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

    if not settings.BLOOD_TYPE_RE.match(blood_type.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid blood type."
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

    if not blood_type.strip():
        raise HTTPException(status_code=400, detail="Blood type cannot be empty.")

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
        "id": studentId,
        "username": username.strip(),
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "address": address.strip(),
        "blood_type": blood_type.strip(),
        "sex": sex_enum,
        "dob": dob,
        "parent_id": parent_uuid,
        "class_id": class_uuid,
        "grade_id": grade_uuid
    }

    result = await StudentUpdate(student_data, processed_img, session)
    return result


@router.delete("/delete", response_model=StudentDeleteResponse)
def softDeleteStudent(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = studentSoftDelete(id, session)
    return result


# ===================== Parent: Lightweight Children List =====================

@router.get("/children", response_model=List[ChildItem])
def getChildren(current_user: ParentUser, session: SessionDep):
    """
    Parent only: Returns lightweight list of all children for the child-selector dropdown.
    Includes graduated children so parents can still access historical data.
    """
    parent, _ = current_user
    return getChildrenOfParentLightweight(parent.id, session)


# ===================== Admin: Bulk Promotion =====================

@router.post("/bulk-promote", response_model=BulkPromoteResponse)
def bulkPromote(data: BulkPromoteRequest, current_user: AdminUser, session: SessionDep):
    """
    Admin: Promote all active students to the next grade.
    - Snapshots current class/grade into StudentClassHistory for 'from_year'.
    - Assigns section-matching class in next grade (e.g. 9-A → 10-A) if it exists.
    - Marks students in the final grade as 'graduated'.
    - Set dry_run=true to preview without writing to the database.
    """
    return bulkPromoteStudents(data.from_year_id, data.to_year_id, data.dry_run, session)


# ===================== Admin: Manual Class Override =====================

@router.patch("/{student_id}/assign-class", response_model=SaveResponse)
def assignClass(
    student_id: uuid.UUID,
    data: AssignClassRequest,
    current_user: AdminUser,
    session: SessionDep,
):
    """
    Admin: Manually assign a student to a specific class.
    Updates both the student record and the StudentClassHistory entry for the given year.
    Defaults to the active academic year if academic_year_id is not supplied.
    """
    return assignClassToStudent(student_id, data.class_id, data.academic_year_id, session)


# ===================== Student Self: Year Data =====================

@router.get("/self/year-data/{academic_year_id}", response_model=StudentYearDataResponse)
def getMyYearData(
    academic_year_id: uuid.UUID,
    current_user: StudentOrParentOrAdminUser,
    session: SessionDep,
):
    """
    Student self-service: Return year data (attendance, results, lessons) for the authenticated student.
    """
    from models import Class, Grade
    from sqlmodel import select as _select
    user, role = current_user
    if role != "student":
        raise HTTPException(status_code=403, detail="Only students can access this endpoint.")
    student_id = user.id

    year = getAcademicYearById(academic_year_id, session)
    if not year:
        raise HTTPException(status_code=404, detail="Academic year not found.")

    attendance = getStudentAttendanceByDateRange(
        student_id, year.start_date, year.end_date, session
    )
    attendance_summary = getStudentYearAttendanceSummary(
        student_id, year.start_date, year.end_date, session
    )
    results = getStudentResultsByDateRange(
        student_id, year.start_date, year.end_date, session
    )
    lessons = getHistoricalLessons(student_id, academic_year_id, session)

    from repository.studentClassHistory import getStudentClassHistoryByYear
    from schemas import ClassBase, GradeBase, LessonBase, AcademicYearBase
    history = getStudentClassHistoryByYear(student_id, academic_year_id, session)
    class_id = history.class_id if history else None
    grade_id = history.grade_id if history else None
    class_name = None
    grade_level = None
    if class_id:
        cls = session.get(Class, class_id)
        class_name = cls.name if cls else None
    if grade_id:
        grd = session.get(Grade, grade_id)
        grade_level = grd.level if grd else None

    return StudentYearDataResponse(
        academic_year=AcademicYearBase.model_validate(year),
        class_id=class_id,
        class_name=class_name,
        grade_id=grade_id,
        grade_level=grade_level,
        attendance=attendance,
        attendance_summary=attendance_summary,
        results=results,
        lessons=[LessonBase.model_validate(l) for l in lessons],
    )


# ===================== Historical Year Data Endpoint =====================

@router.get("/{student_id}/year-data/{academic_year_id}", response_model=StudentYearDataResponse)
def getStudentYearData(
    student_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    current_user: StudentOrTeacherOrAdminUser,  # parents checked separately below
    session: SessionDep,
):
    """
    Return attendance, results, and lessons for a student in a specific academic year.
    Used by the historical year selector on the parent/student dashboard.
    """
    from models import Class, Grade
    from sqlmodel import select as _select

    year = getAcademicYearById(academic_year_id, session)
    if not year:
        raise HTTPException(status_code=404, detail="Academic year not found.")

    attendance = getStudentAttendanceByDateRange(
        student_id, year.start_date, year.end_date, session
    )
    attendance_summary = getStudentYearAttendanceSummary(
        student_id, year.start_date, year.end_date, session
    )
    results = getStudentResultsByDateRange(
        student_id, year.start_date, year.end_date, session
    )
    lessons = getHistoricalLessons(student_id, academic_year_id, session)

    # Resolve class/grade info from StudentClassHistory
    from repository.studentClassHistory import getStudentClassHistoryByYear
    from schemas import ClassBase, GradeBase, LessonBase
    history = getStudentClassHistoryByYear(student_id, academic_year_id, session)
    class_id = history.class_id if history else None
    grade_id = history.grade_id if history else None
    class_name = None
    grade_level = None
    if class_id:
        cls = session.get(Class, class_id)
        class_name = cls.name if cls else None
    if grade_id:
        grd = session.get(Grade, grade_id)
        grade_level = grd.level if grd else None

    from schemas import AcademicYearBase
    return StudentYearDataResponse(
        academic_year=AcademicYearBase.model_validate(year),
        class_id=class_id,
        class_name=class_name,
        grade_id=grade_id,
        grade_level=grade_level,
        attendance=attendance,
        attendance_summary=attendance_summary,
        results=results,
        lessons=[LessonBase.model_validate(l) for l in lessons],
    )


# ===================== Student Class History =====================

@router.get("/{student_id}/history", response_model=StudentHistoryResponse)
def getClassHistory(student_id: uuid.UUID, current_user: AdminUser, session: SessionDep):
    """Admin: Get full class/grade progression history for a student."""
    from repository.student import getStudentByIdAndIsDeleteFalse
    student = getStudentByIdAndIsDeleteFalse(student_id, session)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    history = getStudentFullHistory(student_id, session)
    return StudentHistoryResponse(
        student_id=student_id,
        student_name=f"{student.first_name} {student.last_name}",
        history=history,
    )
