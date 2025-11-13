from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Subject


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