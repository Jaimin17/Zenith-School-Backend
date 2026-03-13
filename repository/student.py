import uuid
from typing import Optional, List

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlmodel import Session, select, or_
from sqlalchemy import func, Select

from core.FileStorage import process_and_save_image, cleanup_image
from core.config import settings
from core.security import get_password_hash
from models import Student, Teacher, Lesson, Class, Parent, Grade, Result, Attendance, UserSex, AcademicYear, StudentClassHistory, StudentStatus
from schemas import StudentSave, StudentUpdateBase, PaginatedStudentResponse, updatePasswordModel, ChildItem, BulkPromoteResponse, PromoteStudentResult


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Student.username).like(search_pattern)) |
            (func.lower(Student.first_name).like(search_pattern)) |
            (func.lower(Student.last_name).like(search_pattern))
        )

    return query


def countStudent(session: Session):
    count_boys_query = (
        select(func.count()).select_from(Student).where(
            Student.is_delete == False,
            Student.sex == UserSex.MALE,
        )
    )

    count_boys = session.exec(count_boys_query).first()

    count_girls_query = (
        select(func.count()).select_from(Student).where(
            Student.is_delete == False,
            Student.sex == UserSex.FEMALE,
        )
    )

    count_girls = session.exec(count_girls_query).first()

    return {
        "boys": count_boys,
        "girls": count_girls
    }


def getStudentByIdAndIsDeleteFalse(studentId: uuid.UUID, session: Session):
    query = (
        select(Student)
        .where(Student.id == studentId, Student.is_delete == False)
    )

    studentDetail = session.exec(query).first()
    return studentDetail


def countStudentBySexAll(session: Session):
    query = (
        select(Student.sex, func.count())
        .select_from(Student)
        .where(Student.is_delete == False)
        .group_by(Student.sex)
    )

    results = session.exec(query).all()
    return {sex: count for sex, count in results}


def getAllStudentsIsDeleteFalse(session: Session, search: str, page: int, year_id: uuid.UUID = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    if year_id:
        count_query = (
            select(func.count(Student.id.distinct()))
            .join(StudentClassHistory, onclause=(StudentClassHistory.student_id == Student.id))
            .where(
                Student.is_delete == False,
                StudentClassHistory.academic_year_id == year_id,
            )
        )
    else:
        count_query = (
            select(func.count(Student.id.distinct()))
            .where(Student.is_delete == False)
        )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    if year_id:
        query = (
            select(Student)
            .join(StudentClassHistory, onclause=(StudentClassHistory.student_id == Student.id))
            .where(
                Student.is_delete == False,
                StudentClassHistory.academic_year_id == year_id,
            )
        )
    else:
        query = (
            select(Student)
            .where(Student.is_delete == False)
        )

    query = query.order_by(func.lower(Student.username))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_students = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedStudentResponse(
        data=active_students,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllStudentsOfTeacherAndIsDeleteFalse(session: Session, teacherId: uuid.UUID, search: str, page: int, year_id: uuid.UUID = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    if year_id:
        count_query = (
            select(func.count(Student.id.distinct()))
            .join(StudentClassHistory, onclause=(StudentClassHistory.student_id == Student.id))
            .join(Lesson, onclause=(Lesson.class_id == StudentClassHistory.class_id))
            .where(
                Student.is_delete == False,
                StudentClassHistory.academic_year_id == year_id,
                Lesson.teacher_id == teacherId,
                Lesson.is_delete == False,
            )
        )
    else:
        count_query = (
            select(func.count(Student.id.distinct()))
            .join(Class, onclause=(Class.id == Student.class_id))
            .join(Lesson, onclause=(Lesson.class_id == Class.id))
            .where(
                Student.is_delete == False,
                Lesson.teacher_id == teacherId,
            )
        )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    if year_id:
        query = (
            select(Student)
            .join(StudentClassHistory, onclause=(StudentClassHistory.student_id == Student.id))
            .join(Lesson, onclause=(Lesson.class_id == StudentClassHistory.class_id))
            .where(
                Student.is_delete == False,
                StudentClassHistory.academic_year_id == year_id,
                Lesson.teacher_id == teacherId,
                Lesson.is_delete == False,
            )
            .distinct()
        )
    else:
        query = (
            select(Student)
            .join(Class, onclause=(Class.id == Student.class_id))
            .join(Lesson, onclause=(Lesson.class_id == Class.id))
            .where(
                Lesson.teacher_id == teacherId,
                Student.is_delete == False,
            )
            .distinct()
        )

    query = query.order_by(Student.username)
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    results = session.exec(query).all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedStudentResponse(
        data=results,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllStudentsOfParentAndIsDeleteFalse(session: Session, parentId: uuid.UUID, search: str, page: int, year_id: uuid.UUID = None):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    if year_id:
        count_query = (
            select(func.count(Student.id.distinct()))
            .join(StudentClassHistory, onclause=(StudentClassHistory.student_id == Student.id))
            .where(
                Student.parent_id == parentId,
                Student.is_delete == False,
                StudentClassHistory.academic_year_id == year_id,
            )
        )
    else:
        count_query = (
            select(func.count(Student.id.distinct()))
            .where(
                Student.parent_id == parentId,
                Student.is_delete == False,
            )
        )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    if year_id:
        query = (
            select(Student)
            .join(StudentClassHistory, onclause=(StudentClassHistory.student_id == Student.id))
            .where(
                Student.parent_id == parentId,
                Student.is_delete == False,
                StudentClassHistory.academic_year_id == year_id,
            )
            .distinct()
        )
    else:
        query = (
            select(Student)
            .where(
                Student.parent_id == parentId,
                Student.is_delete == False,
            )
            .distinct()
        )

    query = query.order_by(Student.username)
    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    results = session.exec(query).all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedStudentResponse(
        data=results,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


async def getAllStudentsOfClassAndIsDeleteFalse(classId: uuid.UUID, session: Session):
    query = (
        select(Student)
        .where(
            Student.is_delete == False,
            Student.class_id == classId,
        )
    )

    query = query.order_by(Student.username)

    results = session.exec(query).all()
    return results


async def studentSaveWithImage(student_data: dict, img: Optional[UploadFile], session: Session):
    username = student_data["username"].strip()
    email = student_data["email"].strip().lower()
    phone = student_data["phone"].strip()

    if not settings.PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail="Invalid Indian phone number. Must be 10 digits starting with 6-9.")

    duplicate_query = (
        select(Student)
        .where(
            or_(
                func.lower(func.trim(Student.username)) == username.lower(),
                func.lower(func.trim(Student.email)) == email,
                func.trim(Student.phone) == phone
            ),
            Student.is_delete == False
        )
    )

    existing: Optional[Student] = session.exec(duplicate_query).first()

    if existing:
        # Provide more specific error message
        if existing.username.lower() == username.lower():
            raise HTTPException(status_code=400, detail="Username already exists.")
        elif existing.email.lower() == email:
            raise HTTPException(status_code=400, detail="Email already exists.")
        else:
            raise HTTPException(status_code=400, detail="Phone number already exists.")

    parent_query = (
        select(Parent)
        .where(Parent.is_delete == False, Parent.id == student_data["parent_id"])
    )

    parent_detail: Optional[Parent] = session.exec(parent_query).first()

    if not parent_detail:
        raise HTTPException(status_code=404, detail="Parent not found with the provided ID.")

    class_query = (
        select(Class)
        .where(Class.is_delete == False, Class.id == student_data["class_id"])
    )

    class_detail: Optional[Class] = session.exec(class_query).first()

    if not class_detail:
        raise HTTPException(status_code=404, detail="Class not found with the provided ID.")

        # Check class capacity
    current_student_count = len([s for s in class_detail.students if not s.is_delete]) if class_detail.students else 0

    if current_student_count >= class_detail.capacity:
        raise HTTPException(
            status_code=400,
            detail=f"Class is full. Current capacity: {current_student_count}/{class_detail.capacity}"
        )

    grades_query = (
        select(Grade)
        .where(Grade.is_delete == False, Grade.id == student_data["grade_id"])
    )

    grade_detail: Optional[Grade] = session.exec(grades_query).first()

    if not grade_detail:
        raise HTTPException(status_code=404, detail="Grade not found with the provided ID.")

    image_filename = None
    if img and img.filename:
        try:
            image_filename = await process_and_save_image(img, "students", username)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

    hashed_password = get_password_hash(student_data["password"].strip())

    new_student = Student(
        username=username,
        first_name=student_data["first_name"].strip(),
        last_name=student_data["last_name"].strip(),
        email=email,
        phone=phone,
        address=student_data["address"].strip(),
        img=image_filename,
        blood_type=student_data["blood_type"],
        sex=student_data["sex"],
        dob=student_data["dob"],
        is_delete=False,
        password=hashed_password,  # or generate one, depending on your logic
        parent_id=student_data["parent_id"],
        class_id=student_data["class_id"],
        grade_id=student_data["grade_id"]
    )

    session.add(new_student)

    try:
        session.flush()  # ensure new_subject.id is generated

        # Auto-create StudentClassHistory entry for the active academic year
        active_year = session.exec(
            select(AcademicYear).where(
                AcademicYear.is_active == True,
                AcademicYear.is_delete == False,
            )
        ).first()
        if active_year:
            history = StudentClassHistory(
                student_id=new_student.id,
                academic_year_id=active_year.id,
                class_id=new_student.class_id,
                grade_id=new_student.grade_id,
            )
            session.add(history)

        session.commit()
    except IntegrityError as e:
        session.rollback()

        if image_filename:
            image_path = settings.UPLOAD_DIR_DP / "students" / image_filename
            cleanup_image(image_path)
        raise HTTPException(
            status_code=400,
            detail="Database error: Unique constraint violated."
        )

    session.refresh(new_student)

    return {
        "id": str(new_student.id),
        "message": "Student created successfully"
    }


def updateStudentPassword(data: updatePasswordModel, session: Session):
    query = (
        select(Student)
        .where(
            Student.is_delete == False,
            Student.id == data.id
        )
    )

    current_user: Optional[Student] = session.exec(query).first()

    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    updatedHashPassword = get_password_hash(data.password)

    current_user.password = updatedHashPassword
    session.add(current_user)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error while updating password."
        )

    return "Password updated successfully"


async def StudentUpdate(student_data: dict, img: Optional[UploadFile], session: Session):
    file_name = img
    print(file_name)

    findStudentQuery = (
        select(Student)
        .where(Student.id == student_data["id"], Student.is_delete == False)
    )

    currentStudent = session.exec(findStudentQuery).first()

    if currentStudent is None:
        raise HTTPException(status_code=404, detail="No student found with the provided ID.")

    new_username = student_data["username"].strip()
    new_email = student_data["email"].strip().lower()
    new_phone = student_data["phone"].strip()

    findSameStudentQuery = (
        select(Student)
        .where(
            or_(
                func.lower(func.trim(Student.username)) == new_username.lower(),
                func.lower(func.trim(Student.email)) == new_email,
                func.trim(Student.phone) == new_phone
            ),
            Student.is_delete == False,
            Student.id != student_data["id"]
        )
    )

    existing: Optional[Student] = session.exec(findSameStudentQuery).first()

    if existing:
        # Determine which field is duplicated
        if existing.username.lower() == new_username.lower():
            raise HTTPException(
                status_code=409,
                detail="A student with this username already exists."
            )
        elif existing.email.lower() == new_email:
            raise HTTPException(
                status_code=409,
                detail="A student with this email already exists."
            )
        else:
            raise HTTPException(
                status_code=409,
                detail="A student with this phone number already exists."
            )

    # Validate parent_id
    parent_query = select(Parent).where(
        Parent.id == student_data["parent_id"],
        Parent.is_delete == False
    )
    parent = session.exec(parent_query).first()
    if not parent:
        raise HTTPException(
            status_code=404,
            detail=f"No parent found with ID: {student_data['parent_id']}"
        )

    # Validate class_id
    class_query = select(Class).where(
        Class.id == student_data["class_id"],
        Class.is_delete == False
    )
    related_class: Optional[Class] = session.exec(class_query).first()
    if not related_class:
        raise HTTPException(
            status_code=404,
            detail=f"No class found with ID: {student_data['class_id']}"
        )

    if currentStudent.class_id != student_data["class_id"]:
        # Count current students in the target class (excluding soft-deleted)
        current_students_count = len([s for s in related_class.students if not s.is_delete])

        if current_students_count >= related_class.capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Class '{related_class.name}' is already full (capacity: {related_class.capacity})."
            )

    # Validate grade_id
    grade_query = select(Grade).where(
        Grade.id == student_data["grade_id"],
        Grade.is_delete == False
    )
    grade = session.exec(grade_query).first()
    if not grade:
        raise HTTPException(
            status_code=404,
            detail=f"No grade found with ID: {student_data['grade_id']}"
        )

    image_filename = currentStudent.img
    if img and img.filename:
        try:
            image_filename = await process_and_save_image(img, "students", new_username)

            if currentStudent.img and currentStudent.img != image_filename:
                old_image_path = settings.UPLOAD_DIR_DP / "students" / currentStudent.img
                cleanup_image(old_image_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

    currentStudent.username = new_username
    currentStudent.first_name = student_data["first_name"]
    currentStudent.last_name = student_data["last_name"]
    currentStudent.email = new_email
    currentStudent.phone = new_phone
    currentStudent.address = student_data["address"]
    currentStudent.img = image_filename
    currentStudent.blood_type = student_data["blood_type"]
    currentStudent.sex = student_data["sex"]
    currentStudent.dob = student_data["dob"]
    currentStudent.parent_id = student_data["parent_id"]
    currentStudent.class_id = student_data["class_id"]
    currentStudent.grade_id = student_data["grade_id"]

    session.add(currentStudent)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if img and img.filename and image_filename != currentStudent.img:
            new_image_path = settings.UPLOAD_DIR_DP / "students" / image_filename
            cleanup_image(new_image_path)

        raise HTTPException(
            status_code=409,
            detail="Database integrity error: Username, email, or phone already exists."
        )

    session.refresh(currentStudent)

    return {
        "id": str(currentStudent.id),
        "message": "Student updated successfully"
    }


def studentSoftDelete(id: uuid.UUID, session: Session):
    findStudent = (
        select(Student)
        .where(Student.id == id, Student.is_delete == False)
    )

    currentStudent: Optional[Student] = session.exec(findStudent).first()

    if currentStudent is None:
        raise HTTPException(status_code=404, detail="No student found with the provided ID.")

    parent_removed = 1 if currentStudent.parent_id is not None else 0
    class_removed = 1 if currentStudent.class_id is not None else 0
    grade_removed = 1 if currentStudent.grade_id is not None else 0

    currentStudent.parent_id = None
    currentStudent.class_id = None
    currentStudent.grade_id = None

    attendance_query = (
        select(Attendance)
        .where(Attendance.student_id == id, Attendance.is_delete == False)
    )
    attendances: List[Attendance] = session.exec(attendance_query).all()
    attendance_count = 0
    for attendance in attendances:
        attendance.is_delete = True
        session.add(attendance)
        attendance_count += 1

    result_query = (
        select(Result)
        .where(Result.student_id == id, Result.is_delete == False)
    )
    results: List[Result] = session.exec(result_query).all()
    result_count = 0
    for result in results:
        result.is_delete = True
        session.add(result)
        result_count += 1

    # Soft delete the student
    currentStudent.is_delete = True
    session.add(currentStudent)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Error deleting student and related records.")

    # Refresh to get latest relationships (optional)
    session.refresh(currentStudent)

    return {
        "id": str(currentStudent.id),
        "message": "Student deleted successfully.",
        "parent_removed": parent_removed,
        "class_removed": class_removed,
        "grade_removed": grade_removed,
        "attendance_affected": attendance_count,
        "result_affected": result_count
    }


# ─────────────────────────────────────────────────────────────────────────────
# Lightweight children list for parent dropdown
# ─────────────────────────────────────────────────────────────────────────────

def getChildrenOfParentLightweight(parent_id: uuid.UUID, session: Session) -> List[ChildItem]:
    """Return minimal student info for the child-selector dropdown (no pagination)."""
    students = session.exec(
        select(Student).where(
            Student.parent_id == parent_id,
            Student.is_delete == False,
        ).order_by(Student.first_name)
    ).all()
    return [
        ChildItem(
            id=s.id,
            first_name=s.first_name,
            last_name=s.last_name,
            username=s.username,
            img=s.img,
            status=s.status,
        )
        for s in students
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Bulk student promotion
# ─────────────────────────────────────────────────────────────────────────────

def bulkPromoteStudents(
    from_year_id: uuid.UUID,
    to_year_id: uuid.UUID,
    dry_run: bool,
    session: Session,
) -> BulkPromoteResponse:
    # ── validate years ──
    from_year = session.exec(
        select(AcademicYear).where(AcademicYear.id == from_year_id, AcademicYear.is_delete == False)
    ).first()
    if not from_year:
        raise HTTPException(status_code=404, detail="Source academic year not found.")

    to_year = session.exec(
        select(AcademicYear).where(AcademicYear.id == to_year_id, AcademicYear.is_delete == False)
    ).first()
    if not to_year:
        raise HTTPException(status_code=404, detail="Target academic year not found.")

    # ── chronological check: from_year must start before to_year ──
    if from_year.start_date >= to_year.start_date:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source year '{from_year.year_label}' must start before the target year "
                f"'{to_year.year_label}'. Check year start dates."
            ),
        )

    # ── fetch all StudentClassHistory records for from_year ──
    from_year_histories = session.exec(
        select(StudentClassHistory).where(
            StudentClassHistory.academic_year_id == from_year_id,
        )
    ).all()

    if not from_year_histories:
        return BulkPromoteResponse(
            dry_run=dry_run,
            from_year=from_year.year_label,
            to_year=to_year.year_label,
            promoted_count=0,
            graduated_count=0,
            skipped_count=0,
            class_not_found_count=0,
            error_count=0,
            total=0,
            results=[],
        )

    # Pre-fetch max grade level to detect final grade dynamically
    max_level_row = session.exec(
        select(func.max(Grade.level)).where(Grade.is_delete == False)
    ).first()
    max_level: int = max_level_row if max_level_row is not None else 0

    # Pre-fetch all grades and classes (avoid N+1)
    all_grades = {g.level: g for g in session.exec(select(Grade).where(Grade.is_delete == False)).all()}
    all_classes = session.exec(select(Class).where(Class.is_delete == False)).all()
    # Map (grade_id, section) -> Class for fast lookup
    class_by_grade_section: dict = {}
    for cls in all_classes:
        if cls.grade_id and "-" in cls.name:
            section = cls.name.split("-", 1)[-1].strip()
            class_by_grade_section[(cls.grade_id, section)] = cls

    results: List[PromoteStudentResult] = []
    promoted_count = graduated_count = skipped_count = class_not_found_count = error_count = 0

    for history in from_year_histories:
        student_id = history.student_id
        student = session.get(Student, student_id)
        if not student or student.is_delete:
            continue  # skip deleted students silently

        try:
            # ── idempotency: skip if student already has a to_year history record ──
            existing_to_year = session.exec(
                select(StudentClassHistory).where(
                    StudentClassHistory.student_id == student_id,
                    StudentClassHistory.academic_year_id == to_year_id,
                )
            ).first()
            if existing_to_year:
                skipped_count += 1
                results.append(PromoteStudentResult(
                    student_id=student.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    action="skipped",
                    detail="Already enrolled in the target academic year.",
                ))
                continue

            # ── use the from_year history's grade_id (snapshot of grade in from_year) ──
            current_level = None
            if history.grade_id:
                grade_obj = session.get(Grade, history.grade_id)
                current_level = grade_obj.level if grade_obj else None

            # ── previous class name from from_year history ──
            previous_class_name = None
            if history.class_id:
                prev_class = session.get(Class, history.class_id)
                previous_class_name = prev_class.name if prev_class else None

            # ── determine next grade ──
            if current_level is None or current_level >= max_level:
                # Final grade → graduate
                if not dry_run:
                    history_record = StudentClassHistory(
                        student_id=student_id,
                        academic_year_id=to_year_id,
                        class_id=None,
                        grade_id=None,
                    )
                    session.add(history_record)
                    if to_year.is_active:
                        student.status = StudentStatus.GRADUATED
                        student.class_id = None
                        session.add(student)
                graduated_count += 1
                results.append(PromoteStudentResult(
                    student_id=student.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    action="graduated",
                    from_grade_level=current_level,
                    previous_class_name=previous_class_name,
                ))
                continue

            next_level = current_level + 1
            next_grade = all_grades.get(next_level)
            if not next_grade:
                # Gap in grade levels — treat as graduated
                if not dry_run:
                    history_record = StudentClassHistory(
                        student_id=student_id,
                        academic_year_id=to_year_id,
                        class_id=None,
                        grade_id=None,
                    )
                    session.add(history_record)
                    if to_year.is_active:
                        student.status = StudentStatus.GRADUATED
                        student.class_id = None
                        session.add(student)
                graduated_count += 1
                results.append(PromoteStudentResult(
                    student_id=student.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    action="graduated",
                    from_grade_level=current_level,
                    previous_class_name=previous_class_name,
                    detail=f"No grade {next_level} exists — treated as graduated.",
                ))
                continue

            # ── section-matching: try to assign same section in next grade ──
            next_class = None
            assigned_class_name = None
            section_missing = False

            if history.class_id:
                current_class = session.get(Class, history.class_id)
                if current_class and "-" in current_class.name:
                    section = current_class.name.split("-", 1)[-1].strip()
                    next_class = class_by_grade_section.get((next_grade.id, section))
                    if next_class:
                        assigned_class_name = next_class.name
                    else:
                        section_missing = True

            if not dry_run:
                # Create to_year history record
                history_record = StudentClassHistory(
                    student_id=student_id,
                    academic_year_id=to_year_id,
                    class_id=next_class.id if next_class else None,
                    grade_id=next_grade.id,
                )
                session.add(history_record)
                # Update student's live state only if to_year is the active year
                if to_year.is_active:
                    student.grade_id = next_grade.id
                    student.class_id = next_class.id if next_class else None
                    session.add(student)

            if section_missing:
                class_not_found_count += 1

            promoted_count += 1
            results.append(PromoteStudentResult(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                action="promoted",
                from_grade_level=current_level,
                to_grade_level=next_level,
                previous_class_name=previous_class_name,
                class_assigned=assigned_class_name,
                class_not_found=section_missing,
                detail="Section not found in next grade — class set to unassigned." if section_missing else None,
            ))

        except Exception as exc:
            error_count += 1
            results.append(PromoteStudentResult(
                student_id=student.id,
                student_name=f"{student.first_name} {student.last_name}",
                action="error",
                detail=str(exc),
            ))

    if not dry_run:
        try:
            session.commit()
        except Exception as exc:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Commit failed: {str(exc)}")

    total = promoted_count + graduated_count + skipped_count + error_count
    return BulkPromoteResponse(
        dry_run=dry_run,
        from_year=from_year.year_label,
        to_year=to_year.year_label,
        promoted_count=promoted_count,
        graduated_count=graduated_count,
        skipped_count=skipped_count,
        class_not_found_count=class_not_found_count,
        error_count=error_count,
        total=total,
        results=results,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Manual class assignment override
# ─────────────────────────────────────────────────────────────────────────────

def assignClassToStudent(
    student_id: uuid.UUID,
    class_id: uuid.UUID,
    academic_year_id: Optional[uuid.UUID],
    session: Session,
) -> dict:
    student = session.exec(
        select(Student).where(Student.id == student_id, Student.is_delete == False)
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    new_class = session.exec(
        select(Class).where(Class.id == class_id, Class.is_delete == False)
    ).first()
    if not new_class:
        raise HTTPException(status_code=404, detail="Class not found.")

    # Determine the year to update history for
    year_id = academic_year_id
    if not year_id:
        active_year = session.exec(
            select(AcademicYear).where(
                AcademicYear.is_active == True,
                AcademicYear.is_delete == False,
            )
        ).first()
        if active_year:
            year_id = active_year.id

    # Update student current class
    student.class_id = class_id
    session.add(student)

    # Update corresponding history record if it exists
    if year_id:
        history = session.exec(
            select(StudentClassHistory).where(
                StudentClassHistory.student_id == student_id,
                StudentClassHistory.academic_year_id == year_id,
            )
        ).first()
        if history:
            history.class_id = class_id
            session.add(history)

    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign class: {str(exc)}")

    return {"id": str(student_id), "message": f"Class '{new_class.name}' assigned successfully."}
