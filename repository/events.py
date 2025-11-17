from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Event, Class


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (
                func.lower(Event.title).like(search_pattern) |
                func.lower(Event.description).like(search_pattern)
            ) | (
                func.lower(Class.name).like(search_pattern)
            )
        )

    return query

def getAllEventsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Event)
        .join(Class, onclause=(Class.id == Event.class_id))
        .where(Event.is_delete == False)
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    events = session.exec(query).unique().all()
    return events