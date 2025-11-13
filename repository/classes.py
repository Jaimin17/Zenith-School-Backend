import uuid
from idlelib import query

from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Class, Teacher


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(Class.name).like(search_pattern)
        )

    return query

def getAllClassesIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Class)
        .where(Class.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_classes = session.exec(query).all()
    return all_classes

def getAllClassOfTeacherAndIsDeleteFalse(supervisorId: uuid.UUID, session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Class)
        .where(
            Class.supervisor_id == supervisorId,
            Class.is_delete == False,
        )
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    all_classes = session.exec(query).all()
    return all_classes