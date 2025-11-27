import uuid

from fastapi import HTTPException
from sqlalchemy import Select, func
from sqlmodel import Session, select, insert

from core.config import settings
from models import Subject
from schemas import SubjectSave, SubjectBase


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Subject.name).like(search_pattern)
        )

    return query

def getAllSubjectsIsDeleteFalse(session: Session, search: str = None, page: int = 1):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Subject)
        .where(Subject.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_subjects = session.exec(query).all()
    return active_subjects

def subjectSave(subject: SubjectSave, session: Session):
    query = (
        select(Subject)
        .where(func.lower(Subject.name) == subject.name.lower(), Subject.is_delete == False)
    )

    existing = session.exec(query).first()

    if existing:
        raise HTTPException(status_code=400, detail="Subject already exists")

    # 2. Create subject
    new_subject = Subject(name=subject.name)
    session.add(new_subject)
    session.flush()  # ensure new_subject.id is generated

    session.commit()
    session.refresh(new_subject)

    return {
        "id": str(new_subject.id),
        "message": "Subject created successfully"
    }

def SubjectUpdate(data: SubjectBase, session: Session):
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

    currentSubject.name = data.name

    session.add(currentSubject)
    session.commit()
    session.refresh(currentSubject)

    return {
        "id": str(currentSubject.id),
        "message": "Subject updated successfully"
    }

def SubjectSoftDelete(id: uuid.UUID, session: Session):
    findSubject = (
        select(Subject)
        .where(Subject.id == id, Subject.is_delete == False)
    )

    currentSubject = session.exec(findSubject).first()

    if currentSubject is None:
        raise HTTPException(status_code=404, detail="No subject found with the provided ID.")

    currentSubject.is_delete = True

    session.add(currentSubject)
    session.commit()
    session.refresh(currentSubject)

    return {
        "id": str(currentSubject.id),
        "message": "Subject deleted successfully"
    }