from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Parent


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (func.lower(Parent.username).like(search_pattern)) |
            (func.lower(Parent.first_name).like(search_pattern)) |
            (func.lower(Parent.last_name).like(search_pattern))
        )

    return query

def countParent(session: Session):
    return session.exec(
        select(func.count()).select_from(Parent).where(Parent.is_delete == False)
    ).first()

def getAllParentIsDeleteFalse(session: Session, search: str = None, page: int = 1):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Parent)
        .where(Parent.is_delete == False)
    )

    query = addSearchOption(query, search)

    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    active_parents = session.exec(query).all()
    return active_parents