import uuid

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import Select, func
from sqlmodel import Session, select, insert

from core.config import settings
from models import Subject, Teacher, Lesson, TeacherSubjectLink
from schemas import SubjectSave, SubjectBase, SubjectUpdateBase, PaginatedSubjectResponse


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Subject.name).like(search_pattern)
        )

    return query


def getAllSubjectsIsDeleteFalse(session: Session, search: str = None, page: int = 1):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    count_query = (
        select(func.count(Subject.id.distinct()))
        .where(
            Subject.is_delete == False
        )
    )

    count_query = addSearchOption(count_query, search)
    total_count = session.exec(count_query).one()

    query = (
        select(Subject)
        .where(Subject.is_delete == False)
    )

    query = query.order_by(func.lower(Subject.name))

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_subjects = session.exec(query).all()

    total_pages = (total_count + settings.ITEMS_PER_PAGE - 1) // settings.ITEMS_PER_PAGE

    return PaginatedSubjectResponse(
        data=active_subjects,
        total_pages=total_pages,
        total_count=total_count,
        page=page,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def getListOfAllSubjectIsDeleteFalse(session: Session):
    query = (
        select(Subject)
        .where(Subject.is_delete == False)
    )

    query = query.order_by(func.lower(Subject.name))

    all_subject_list = session.exec(query).all()
    return all_subject_list


def findSubjectById(subjectId: uuid.UUID, session: Session):
    query = (
        select(Subject)
        .where(Subject.id == subjectId, Subject.is_delete == False)
    )

    subject = session.exec(query).first()

    if subject is None:
        raise HTTPException(status_code=404, detail="No subject found with the provided ID.")

    return subject


def countSubjectForTeacher(teacherId: uuid.UUID, session: Session):
    query = (
        select(func.count(TeacherSubjectLink.subject_id))
        .select_from(Teacher)
        .join(TeacherSubjectLink, Teacher.id == TeacherSubjectLink.teacher_id)
        .where(Teacher.id == teacherId, Teacher.is_delete == False)
    )

    result = session.exec(query).one()
    return result


def subjectSave(subject: SubjectSave, session: Session):
    query = (
        select(Subject)
        .where(func.lower(Subject.name) == subject.name.lower(), Subject.is_delete == False)
    )

    existing = session.exec(query).first()

    if existing:
        raise HTTPException(status_code=400, detail="Subject already exists")

    teachers_list_ids = subject.teachersList or []
    if teachers_list_ids:
        teacher_query = (
            select(Teacher)
            .where(Teacher.id.in_(teachers_list_ids), Teacher.is_delete == False)
        )

        teachers = session.exec(teacher_query).all()
        found_ids = {t.id for t in teachers}

        missing = [str(tid) for tid in teachers_list_ids if tid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"No teacher(s) found with the provided ID(s): {', '.join(missing)}"
            )
    else:
        teachers = []

    new_subject = Subject(name=subject.name)
    new_subject.teachers = teachers

    session.add(new_subject)

    try:
        session.flush()  # ensure new_subject.id is generated
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Subject already exists (unique constraint)")

    session.refresh(new_subject)

    return {
        "id": str(new_subject.id),
        "message": "Subject created successfully",
        "lessons_affected": None
    }


def SubjectUpdate(data: SubjectUpdateBase, session: Session):
    findSubjectQuery = (
        select(Subject)
        .where(Subject.id == data.id, Subject.is_delete == False)
    )

    currentSubject = session.exec(findSubjectQuery).first()

    if currentSubject is None:
        raise HTTPException(status_code=404, detail="No subject found with the provided ID.")

    findSameNameSubjectquery = (
        select(Subject)
        .where(func.lower(Subject.name) == data.name.lower(), Subject.is_delete == False, Subject.id != data.id)
    )

    existing = session.exec(findSameNameSubjectquery).first()

    if existing:
        raise HTTPException(status_code=400, detail="A subject with the same name already exists.")

    teachers_list_ids = data.teachersList or []
    if teachers_list_ids:
        teacher_query = (
            select(Teacher)
            .where(Teacher.id.in_(teachers_list_ids), Teacher.is_delete == False)
        )

        teachers = session.exec(teacher_query).all()
        found_ids = {t.id for t in teachers}

        missing = [str(tid) for tid in teachers_list_ids if tid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"No teacher(s) found with the provided ID(s): {', '.join(missing)}"
            )
    else:
        teachers = []

    currentSubject.name = data.name
    currentSubject.teachers = teachers

    session.add(currentSubject)

    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Subject already exists (unique constraint)")

    session.refresh(currentSubject)

    return {
        "id": str(currentSubject.id),
        "message": "Subject updated successfully",
        "lessons_affected": None
    }


def SubjectSoftDelete_with_lesson(id: uuid.UUID, session: Session):
    findSubject = (
        select(Subject)
        .where(Subject.id == id, Subject.is_delete == False)
    )

    currentSubject = session.exec(findSubject).first()

    if currentSubject is None:
        raise HTTPException(status_code=404, detail="No subject found with the provided ID.")

    currentSubject.teachers.clear()

    lesson_query = (
        select(Lesson)
        .where(Lesson.subject_id == id, Lesson.is_delete == False)
    )

    lessons = session.exec(lesson_query).all()

    for lesson in lessons:
        lesson.is_delete = True

    currentSubject.is_delete = True

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Error deleting subject")
    session.refresh(currentSubject)

    return {
        "id": str(currentSubject.id),
        "message": "Subject deleted successfully",
        "lessons_affected": len(lessons)
    }
