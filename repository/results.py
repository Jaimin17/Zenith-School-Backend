import uuid
from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Student, Teacher, Exam, Assignment, Result, Lesson, Class
from schemas import ResultSave, ResultUpdate, PaginatedResultResponse


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (
                    func.lower(Student.username).like(search_pattern) |
                    func.lower(Student.first_name).like(search_pattern) |
                    func.lower(Student.last_name).like(search_pattern)
            ) |
            (
                    func.lower(Teacher.username).like(search_pattern) |
                    func.lower(Teacher.first_name).like(search_pattern) |
                    func.lower(Teacher.last_name).like(search_pattern)
            ) |
            (
                func.lower(Exam.title).like(search_pattern)
            ) |
            (
                func.lower(Assignment.title).like(search_pattern)
            )
        )

    return query


def getAllResultsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Result.id.distinct()))
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Result.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(Result.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedResultResponse(
        data=all_results,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllResultsByTeacherIsDeleteFalse(teacherId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Result.id.distinct()))
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Teacher.id == teacherId,
            Result.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Teacher.id == teacherId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedResultResponse(
        data=all_results,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllResultsOfClassIsDeleteFalse(classId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Result.id.distinct()))
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Lesson.class_id == classId,
            Result.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Lesson.class_id == classId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedResultResponse(
        data=all_results,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllResultsOfStudentIsDeleteFalse(studentId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Result.id.distinct()))
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Result.student_id == studentId,
            Result.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Result.student_id == studentId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedResultResponse(
        data=all_results,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getAllResultsOfParentIsDeleteFalse(parentId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Result.id.distinct()))
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Student.parent_id == parentId,
            Result.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    query = (
        select(Result)
        .join(Student, Student.id == Result.student_id)
        .join(Exam, Exam.id == Result.exam_id, isouter=True)
        .join(Assignment, Assignment.id == Result.assignment_id, isouter=True)
        .join(
            Lesson,
            (Lesson.id == Exam.lesson_id) | (Lesson.id == Assignment.lesson_id),
            isouter=True
        )
        .join(Teacher, Teacher.id == Lesson.teacher_id, isouter=True)
        .where(
            Student.parent_id == parentId,
            Result.is_delete == False
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_results = session.exec(query).unique().all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedResultResponse(
        data=all_results,
        total_count=total_count,
        total_pages=total_pages,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def resultSave(result: ResultSave, userId: uuid.UUID, role: str, session: Session):
    student_query = select(Student).where(
        Student.id == result.student_id,
        Student.is_delete == False
    )
    student = session.exec(student_query).first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail=f"No active student found with ID: {result.student_id}"
        )

    if result.exam_id is not None:
        exam_query = select(Exam).where(
            Exam.id == result.exam_id,
            Exam.is_delete == False
        )
        exam: Optional[Exam] = session.exec(exam_query).first()
        if not exam:
            raise HTTPException(
                status_code=404,
                detail=f"No active exam found with ID: {result.exam_id}"
            )

        if not exam.lesson:
            raise HTTPException(
                status_code=404,
                detail="Exam is not associated with any lesson."
            )

            # Check if student belongs to the same class as the lesson
        if student.class_id != exam.lesson.class_id:
            raise HTTPException(
                status_code=400,
                detail="Student does not belong to the class associated with this exam's lesson."
            )

        if role == "teacher":
            if exam.lesson.teacher_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to add results for this exam."
                )

    if result.assignment_id is not None:
        assignment_query = select(Assignment).where(
            Assignment.id == result.assignment_id,
            Assignment.is_delete == False
        )
        assignment: Optional[Assignment] = session.exec(assignment_query).first()
        if not assignment:
            raise HTTPException(
                status_code=404,
                detail=f"No active assignment found with ID: {result.assignment_id}"
            )

        if not assignment.lesson:
            raise HTTPException(
                status_code=404,
                detail="Assignment is not associated with any lesson."
            )

            # Check if student belongs to the same class as the lesson
        if student.class_id != assignment.lesson.class_id:
            raise HTTPException(
                status_code=400,
                detail="Student does not belong to the class associated with this assignment's lesson."
            )

        if role == "teacher":
            if assignment.lesson.teacher_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to add results for this assignment."
                )

    duplicate_query = select(Result).where(
        Result.student_id == result.student_id,
        Result.is_delete == False
    )

    if result.exam_id is not None:
        duplicate_query = duplicate_query.where(Result.exam_id == result.exam_id)
    else:
        duplicate_query = duplicate_query.where(Result.assignment_id == result.assignment_id)

    existing_result = session.exec(duplicate_query).first()
    if existing_result:
        entity_type = "exam" if result.exam_id else "assignment"
        raise HTTPException(
            status_code=400,
            detail=f"A result already exists for this student and {entity_type}."
        )

    new_result = Result(
        score=result.score,
        assignment_id=result.assignment_id,
        exam_id=result.exam_id,
        student_id=result.student_id,
        is_delete=False
    )

    session.add(new_result)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=409, detail="Result already exists (unique constraint)")

    session.refresh(new_result)

    return {
        "id": str(new_result.id),
        "message": "Result saved successfully"
    }


def resultUpdate(result: ResultUpdate, userId: uuid.UUID, role: str, session: Session):
    result_query = (
        select(Result)
        .where(Result.id == result.id, Result.is_delete == False)
    )

    current_result: Optional[Result] = session.exec(result_query).first()
    if not current_result:
        raise HTTPException(
            status_code=404,
            detail=f"No active result found with ID: {result.id}"
        )

    if role == "teacher":
        if current_result.exam_id:
            exam_query = select(Exam).where(
                Exam.id == current_result.exam_id,
                Exam.is_delete == False
            )
            current_exam = session.exec(exam_query).first()
            if current_exam and current_exam.lesson and current_exam.lesson.teacher_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to update this result."
                )

        # Check if teacher owns the current assignment
        if current_result.assignment_id:
            assignment_query = select(Assignment).where(
                Assignment.id == current_result.assignment_id,
                Assignment.is_delete == False
            )
            current_assignment = session.exec(assignment_query).first()
            if current_assignment and current_assignment.lesson and current_assignment.lesson.teacher_id != userId:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to update this result."
                )

    new_student = None
    if current_result.student_id != result.student_id:
        student_query = select(Student).where(
            Student.id == result.student_id,
            Student.is_delete == False
        )
        new_student = session.exec(student_query).first()
        if not new_student:
            raise HTTPException(
                status_code=404,
                detail=f"No active student found with ID: {result.student_id}"
            )
    else:
        student_query = select(Student).where(
            Student.id == result.student_id,
            Student.is_delete == False
        )
        new_student = session.exec(student_query).first()

    if current_result.exam_id != result.exam_id:
        if result.exam_id is not None:
            exam_query = select(Exam).where(
                Exam.id == result.exam_id,
                Exam.is_delete == False
            )
            exam: Optional[Exam] = session.exec(exam_query).first()
            if not exam:
                raise HTTPException(
                    status_code=404,
                    detail=f"No active exam found with ID: {result.exam_id}"
                )

            if not exam.lesson:
                raise HTTPException(
                    status_code=404,
                    detail="Exam is not associated with any lesson."
                )

                # Check if student belongs to the same class as the lesson
            if new_student and new_student.class_id != exam.lesson.class_id:
                raise HTTPException(
                    status_code=400,
                    detail="Student does not belong to the class associated with this exam's lesson."
                )

            if role == "teacher":
                if exam.lesson.teacher_id != userId:
                    raise HTTPException(
                        status_code=403,
                        detail="You are not authorized to assign results for this exam."
                    )

            current_result.exam_id = result.exam_id
            current_result.assignment_id = None
        else:
            current_result.exam_id = None

    if current_result.assignment_id != result.assignment_id:
        if result.assignment_id is not None:
            assignment_query = select(Assignment).where(
                Assignment.id == result.assignment_id,
                Assignment.is_delete == False
            )
            assignment: Optional[Assignment] = session.exec(assignment_query).first()
            if not assignment:
                raise HTTPException(
                    status_code=404,
                    detail=f"No active assignment found with ID: {result.assignment_id}"
                )

            if not assignment.lesson:
                raise HTTPException(
                    status_code=404,
                    detail="Assignment is not associated with any lesson."
                )

                # Check if student belongs to the same class as the lesson
            if new_student and new_student.class_id != assignment.lesson.class_id:
                raise HTTPException(
                    status_code=400,
                    detail="Student does not belong to the class associated with this assignment's lesson."
                )

            if role == "teacher":
                if assignment.lesson.teacher_id != userId:
                    raise HTTPException(
                        status_code=403,
                        detail="You are not authorized to assign results for this assignment."
                    )

            current_result.assignment_id = result.assignment_id
            current_result.exam_id = None
        else:
            current_result.assignment_id = None

    duplicate_query = select(Result).where(
        Result.student_id == result.student_id,
        Result.id != result.id,
        Result.is_delete == False
    )

    if result.exam_id is not None:
        duplicate_query = duplicate_query.where(Result.exam_id == result.exam_id)
    elif result.assignment_id is not None:
        duplicate_query = duplicate_query.where(Result.assignment_id == result.assignment_id)

    existing_result = session.exec(duplicate_query).first()
    if existing_result:
        entity_type = "exam" if result.exam_id else "assignment"
        raise HTTPException(
            status_code=409,
            detail=f"A result already exists for this student and {entity_type}."
        )

    current_result.score = result.score
    session.add(current_result)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=409, detail="Result already exists (unique constraint)")

    session.refresh(current_result)

    return {
        "id": str(current_result.id),
        "message": "Result updated successfully"
    }


def ResultSoftDelete(id: uuid.UUID, userId: uuid.UUID, role: str, session: Session):
    result_query = (
        select(Result)
        .where(Result.id == id, Result.is_delete == False)
    )

    current_result: Optional[Result] = session.exec(result_query).first()
    if not current_result:
        raise HTTPException(
            status_code=404,
            detail=f"No active result found with ID: {id}"
        )

    if role == "teacher":
        if current_result.exam_id:
            exam_query = select(Exam).where(
                Exam.id == current_result.exam_id,
                Exam.is_delete == False
            )
            exam = session.exec(exam_query).first()
            if exam:
                if not exam.lesson:
                    raise HTTPException(
                        status_code=404,
                        detail="Exam is not associated with any lesson."
                    )
                if exam.lesson.teacher_id != userId:
                    raise HTTPException(
                        status_code=403,
                        detail="You are not authorized to delete this result."
                    )
        if current_result.assignment_id:
            assignment_query = select(Assignment).where(
                Assignment.id == current_result.assignment_id,
                Assignment.is_delete == False
            )
            assignment = session.exec(assignment_query).first()
            if assignment:
                if not assignment.lesson:
                    raise HTTPException(
                        status_code=404,
                        detail="Assignment is not associated with any lesson."
                    )
                if assignment.lesson.teacher_id != userId:
                    raise HTTPException(
                        status_code=403,
                        detail="You are not authorized to delete this result."
                    )

    current_result.is_delete = True
    session.add(current_result)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error deleting result."
        )

    session.refresh(current_result)

    return {
        "id": str(current_result.id),
        "message": "Result soft-deleted successfully."
    }
