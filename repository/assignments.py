import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException, UploadFile
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select, or_, and_

from core.FileStorage import cleanup_pdf, process_and_save_pdf
from core.config import settings
from models import Assignment, Lesson, Class, Student, Result, Subject
from schemas import AssignmentSave, AssignmentUpdate, PaginatedAssignmentResponse


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Assignment.title).like(search_pattern))
        )

    return query


def apply_assignment_filters(
        query,
        subject_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None,
        lesson_already_joined: bool = False
):
    """
    Apply filters to assignment query

    Args:
        query: SQLAlchemy query to filter
        subject_id: Filter by subject UUID
        teacher_id: Filter by teacher UUID
        status: Filter by status (active, upcoming, overdue)
        due_date: Filter by due date (YYYY-MM-DD format)
        lesson_already_joined: Set to True if Lesson table is already joined in the base query
    """

    # Track if we need to join Lesson for filters
    need_lesson_join = (subject_id or teacher_id) and not lesson_already_joined

    # Join Lesson once if needed for subject or teacher filters
    if need_lesson_join:
        query = query.join(Lesson, onclause=(Assignment.lesson_id == Lesson.id), isouter=False)

    # Filter by subject
    if subject_id:
        try:
            subject_uuid = uuid.UUID(subject_id)
            query = query.join(Subject, onclause=(Lesson.subject_id == Subject.id), isouter=False)
            query = query.where(Subject.id == subject_uuid)
        except ValueError:
            pass  # Invalid UUID, skip filter

    # Filter by teacher
    if teacher_id:
        try:
            teacher_uuid = uuid.UUID(teacher_id)
            query = query.where(Lesson.teacher_id == teacher_uuid)
        except ValueError:
            pass  # Invalid UUID, skip filter

    # Filter by status (active, upcoming, overdue)
    if status:
        today = datetime.now().date()

        if status == "overdue":
            query = query.where(Assignment.due_date < today)
        elif status == "upcoming":
            query = query.where(Assignment.start_date > today)
        elif status == "active":
            query = query.where(
                and_(
                    Assignment.start_date <= today,
                    Assignment.due_date >= today
                )
            )

    # Filter by due date
    if due_date:
        try:
            filter_date = datetime.strptime(due_date, "%Y-%m-%d").date()
            query = query.where(func.date(Assignment.due_date) == filter_date)
        except ValueError:
            pass  # Invalid date format, skip filter

    return query


def getAllAssignmentsIsDeleteFalse(
        session: Session,
        search: str,
        page: int,
        subject_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Count query
    count_query = (
        select(func.count(Assignment.id.distinct()))
        .where(Assignment.is_delete == False)
    )

    count_query = addSearchOption(count_query, search)
    # Lesson is NOT already joined, so pass False
    count_query = apply_assignment_filters(
        count_query, subject_id, teacher_id, status, due_date, lesson_already_joined=False
    )
    total_count = session.exec(count_query).one()

    # Data query
    query = (
        select(Assignment)
        .where(Assignment.is_delete == False)
    )

    query = addSearchOption(query, search)
    # Lesson is NOT already joined, so pass False
    query = apply_assignment_filters(
        query, subject_id, teacher_id, status, due_date, lesson_already_joined=False
    )
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedAssignmentResponse(
        data=all_assignments,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAssignmentById(session: Session, assignmentId: uuid.UUID):
    query = (
        select(Assignment)
        .options(
            # Eager load relationships to avoid lazy loading issues
            selectinload(Assignment.lesson).selectinload(Lesson.teacher),
            selectinload(Assignment.lesson).selectinload(Lesson.related_class).selectinload(Class.students)
        )
        .where(
            Assignment.id == assignmentId,
            Assignment.is_delete == False,
        )
    )

    assignment_detail = session.exec(query).first()
    return assignment_detail


def getAllAssignmentsOfTeacherIsDeleteFalse(
        teacherId: uuid.UUID,
        session: Session,
        search: str,
        page: int,
        subject_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Count query - Lesson is already joined
    count_query = (
        select(func.count(Assignment.id.distinct()))
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .where(
            Lesson.teacher_id == teacherId,
            Assignment.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    # Lesson IS already joined, so pass True
    count_query = apply_assignment_filters(
        count_query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    total_count = session.exec(count_query).one()

    # Data query - Lesson is already joined
    query = (
        select(Assignment)
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .where(
            Lesson.teacher_id == teacherId,
            Assignment.is_delete == False,
        )
    )

    query = addSearchOption(query, search)
    # Lesson IS already joined, so pass True
    query = apply_assignment_filters(
        query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedAssignmentResponse(
        data=all_assignments,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllAssignmentsOfParentIsDeleteFalse(
        parentId,
        session,
        search,
        page,
        subject_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Count query - Lesson is already joined
    count_query = (
        select(func.count(Assignment.id.distinct()))
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .join(Class, onclause=(Class.id == Lesson.class_id))
        .join(Student, onclause=(Student.class_id == Class.id))
        .where(
            Student.parent_id == parentId,
            Assignment.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    # Lesson IS already joined, so pass True
    count_query = apply_assignment_filters(
        count_query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    total_count = session.exec(count_query).one()

    # Data query - Lesson is already joined
    query = (
        select(Assignment)
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .join(Class, onclause=(Class.id == Lesson.class_id))
        .join(Student, onclause=(Student.class_id == Class.id))
        .where(
            Student.parent_id == parentId,
            Assignment.is_delete == False,
        )
    )

    query = addSearchOption(query, search)
    # Lesson IS already joined, so pass True
    query = apply_assignment_filters(
        query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedAssignmentResponse(
        data=all_assignments,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllAssignmentsOfClassIsDeleteFalse(
        classId: uuid.UUID,
        session: Session,
        search: str,
        page: int,
        subject_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Count query - Lesson is already joined
    count_query = (
        select(func.count(Assignment.id.distinct()))
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .where(
            Lesson.class_id == classId,
            Assignment.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    # Lesson IS already joined, so pass True
    count_query = apply_assignment_filters(
        count_query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    total_count = session.exec(count_query).one()

    # Data query - Lesson is already joined
    query = (
        select(Assignment)
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .where(
            Lesson.class_id == classId,
            Assignment.is_delete == False,
        )
    )

    query = addSearchOption(query, search)
    # Lesson IS already joined, so pass True
    query = apply_assignment_filters(
        query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedAssignmentResponse(
        data=all_assignments,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllAssignmentsOfStudentIsDeleteFalse(
        studentId: uuid.UUID,
        session: Session,
        search: str,
        page: int,
        subject_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None
):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    # Count query - Lesson is already joined
    count_query = (
        select(func.count(Assignment.id.distinct()))
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .join(Student, onclause=(Student.class_id == Lesson.class_id))
        .where(
            Student.id == studentId,
            Student.is_delete == False,
            Assignment.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    # Lesson IS already joined, so pass True
    count_query = apply_assignment_filters(
        count_query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    total_count = session.exec(count_query).one()

    # Data query - Lesson is already joined
    query = (
        select(Assignment)
        .join(Lesson, onclause=(Assignment.lesson_id == Lesson.id))
        .join(Student, onclause=(Student.class_id == Lesson.class_id))
        .where(
            Student.id == studentId,
            Student.is_delete == False,
            Assignment.is_delete == False
        )
    )

    query = addSearchOption(query, search)
    # Lesson IS already joined, so pass True
    query = apply_assignment_filters(
        query, subject_id, teacher_id, status, due_date, lesson_already_joined=True
    )
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_assignments = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedAssignmentResponse(
        data=all_assignments,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


async def assignmentSaveWithPdf(assignment: AssignmentSave, pdf: UploadFile, userId: uuid.UUID, role: str,
                                session: Session):
    lesson_query = (
        select(Lesson)
        .where(Lesson.id == assignment.lesson_id, Lesson.is_delete == False)
    )
    lesson: Optional[Lesson] = session.exec(lesson_query).first()

    if not lesson:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found with the provided ID."
        )

    if role.lower() == "teacher":
        if lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="Teachers can only create assignment for their own lessons."
            )

    duplicate_title_query = (
        select(Assignment)
        .where(
            Assignment.lesson_id == assignment.lesson_id,
            func.lower(func.trim(Assignment.title)) == assignment.title.strip().lower(),
            Assignment.is_delete == False
        )
    )
    existing_title = session.exec(duplicate_title_query).first()

    if existing_title:
        raise HTTPException(
            status_code=400,
            detail=f"An assignment with the title '{assignment.title}' already exists for this lesson."
        )

    if lesson.class_id:
        # Get all lessons for the same class
        class_lessons_query = (
            select(Lesson)
            .where(
                Lesson.class_id == lesson.class_id,
                Lesson.is_delete == False
            )
        )
        class_lessons = session.exec(class_lessons_query).all()
        class_lesson_ids = [l.id for l in class_lessons]

        if class_lesson_ids:
            # Check for overlapping assignments in any lesson of the same class
            time_conflict_query = (
                select(Assignment)
                .where(
                    Assignment.lesson_id.in_(class_lesson_ids),
                    Assignment.is_delete == False,
                    or_(
                        # New assignment starts during existing assignment
                        and_(
                            Assignment.start_date <= assignment.start_date,
                            Assignment.due_date > assignment.start_date
                        ),
                        # New assignment ends during existing assignment
                        and_(
                            Assignment.start_date < assignment.end_date,
                            Assignment.due_date >= assignment.end_date
                        ),
                        # New assignment completely contains existing assignment
                        and_(
                            Assignment.start_date >= assignment.start_date,
                            Assignment.due_date <= assignment.end_date
                        )
                    )
                )
            )
            conflicting_assignment = session.exec(time_conflict_query).first()

            if conflicting_assignment:
                raise HTTPException(
                    status_code=400,
                    detail=f"Time conflict: Another assignment '{conflicting_assignment.title}' is scheduled for this class at the same time."
                )

    pdf_filename = None
    try:
        pdf_filename = await process_and_save_pdf(pdf, "assignments", assignment.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

    if not pdf_filename:
        raise HTTPException(
            status_code=500,
            detail="Failed to save PDF file."
        )

    new_assignment = Assignment(
        title=assignment.title.strip(),
        start_date=assignment.start_date,
        due_date=assignment.end_date,
        lesson_id=assignment.lesson_id,
        pdf_name=pdf_filename,
        is_delete=False
    )

    session.add(new_assignment)

    try:
        session.flush()
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if pdf_filename:
            pdf_path = settings.UPLOAD_DIR_PDF / "assignments" / pdf_filename
            cleanup_pdf(pdf_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(new_assignment)

    return {
        "id": str(new_assignment.id),
        "message": "Assignment created successfully"
    }


async def assignmentUpdate(assignment: AssignmentUpdate, pdf: Optional[UploadFile], userId: uuid.UUID, role: str,
                           session: Session):
    find_assignment_query = (
        select(Assignment)
        .where(Assignment.id == assignment.id, Assignment.is_delete == False)
    )
    current_assignment: Optional[Assignment] = session.exec(find_assignment_query).first()

    if not current_assignment:
        raise HTTPException(
            status_code=404,
            detail="Assignment not found with the provided ID."
        )

    current_lesson_query = (
        select(Lesson)
        .where(Lesson.id == current_assignment.lesson_id, Lesson.is_delete == False)
    )
    current_lesson: Optional[Lesson] = session.exec(current_lesson_query).first()

    if not current_lesson:
        raise HTTPException(
            status_code=404,
            detail="Associated lesson not found or has been deleted."
        )

    if role.lower() == "teacher":
        if current_lesson.teacher_id != userId:
            raise HTTPException(
                status_code=403,
                detail="Teachers can only update assignment for their own lessons."
            )

    duplicate_title_query = (
        select(Assignment)
        .where(
            Assignment.lesson_id == current_assignment.lesson_id,
            Assignment.id != assignment.id,
            func.lower(func.trim(Assignment.title)) == assignment.title.strip().lower(),
            Assignment.is_delete == False
        )
    )
    existing_title = session.exec(duplicate_title_query).first()

    if existing_title:
        raise HTTPException(
            status_code=400,
            detail=f"An assignment with the title '{assignment.title}' already exists for this lesson."
        )

    current_assignment.title = assignment.title.strip()

    new_lesson = None
    if assignment.lesson_id is not None and assignment.lesson_id != current_assignment.lesson_id:
        # Verify new lesson exists
        new_lesson_query = (
            select(Lesson)
            .where(Lesson.id == assignment.lesson_id, Lesson.is_delete == False)
        )
        new_lesson = session.exec(new_lesson_query).first()

        if not new_lesson:
            raise HTTPException(
                status_code=404,
                detail="New lesson not found with the provided ID."
            )

        # Role-based validation for new lesson
        if role.lower() == "teacher":
            if new_lesson.teacher_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="Teachers can only assign assignment to their own lessons."
                )

        current_assignment.lesson_id = assignment.lesson_id

    lesson_for_conflict_check = new_lesson if new_lesson else current_lesson

    if lesson_for_conflict_check.class_id:
        # Get all lessons for the same class
        class_lessons_query = (
            select(Lesson)
            .where(
                Lesson.class_id == lesson_for_conflict_check.class_id,
                Lesson.is_delete == False
            )
        )
        class_lessons = session.exec(class_lessons_query).all()
        class_lesson_ids = [l.id for l in class_lessons]

        if class_lesson_ids:
            check_start_date = assignment.start_date if assignment.start_date is not None else current_assignment.start_date
            check_due_date = assignment.end_date if assignment.end_date is not None else current_assignment.due_date

            time_conflict_query = (
                select(Assignment)
                .where(
                    Assignment.lesson_id.in_(class_lesson_ids),
                    Assignment.id != assignment.id,  # Exclude current assignment
                    Assignment.is_delete == False,
                    or_(
                        # New assignment starts during existing assignment
                        and_(
                            Assignment.start_date <= check_start_date,
                            Assignment.due_date > check_start_date
                        ),
                        # New assignment ends during existing assignment
                        and_(
                            Assignment.start_date < check_due_date,
                            Assignment.due_date >= check_due_date
                        ),
                        # New assignment completely contains existing assignment
                        and_(
                            Assignment.start_date >= check_start_date,
                            Assignment.due_date <= check_due_date
                        )
                    )
                )
            )
            conflicting_assignment = session.exec(time_conflict_query).first()

            if conflicting_assignment:
                raise HTTPException(
                    status_code=400,
                    detail=f"Time conflict: Another assignment '{conflicting_assignment.title}' is scheduled for this class at the same time."
                )

    if assignment.start_date is not None:
        current_assignment.start_date = assignment.start_date
    if assignment.end_date is not None:
        current_assignment.due_date = assignment.end_date

    old_pdf_filename = current_assignment.pdf_name
    if pdf is not None:
        try:
            pdf_filename = await process_and_save_pdf(pdf, "assignments", assignment.title)
            current_assignment.pdf_name = pdf_filename

            # Clean up old PDF after successful upload
            if old_pdf_filename:
                old_pdf_path = settings.UPLOAD_DIR_PDF / "assignments" / old_pdf_filename
                cleanup_pdf(old_pdf_path)

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

    session.add(current_assignment)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if pdf is not None and current_assignment.pdf_name != old_pdf_filename:
            new_pdf_path = settings.UPLOAD_DIR_PDF / "assignments" / current_assignment.pdf_name
            cleanup_pdf(new_pdf_path)
        raise HTTPException(
            status_code=400,
            detail="Database integrity error. Please check your data."
        )

    session.refresh(current_assignment)

    return {
        "id": str(current_assignment.id),
        "message": "Assignment updated successfully"
    }


def assignmentSoftDelete(id: uuid.UUID, session: Session):
    current_assignment_query = (
        select(Assignment)
        .where(Assignment.id == id, Assignment.is_delete == False)
    )

    current_assignment: Optional[Assignment] = session.exec(current_assignment_query).first()

    if not current_assignment:
        raise HTTPException(
            status_code=404,
            detail="Assignment not found with provided id."
        )

    result_query = (
        select(Result)
        .where(Result.exam_id == id, Result.is_delete == False)
    )
    results: List[Result] = session.exec(result_query).all()

    affected_results = 0
    for result in results:
        result.is_delete = True
        session.add(result)
        affected_results += 1

    current_assignment.is_delete = True
    session.add(current_assignment)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error deleting assignment and related records."
        )

    session.refresh(current_assignment)

    return {
        "id": str(current_assignment.id),
        "message": "Assignment soft-deleted successfully.",
        "result_affected": affected_results
    }
