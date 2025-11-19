from sqlalchemy import Select, func
from sqlmodel import Session, select

from core.config import settings
from models import Announcement, Class, Student


def addSearchOption(query: Select, search: str):
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            (
                func.lower(Announcement.title).like(search_pattern) |
                func.lower(Announcement.description).like(search_pattern)
            ) | (
                func.lower(Class.name).like(search_pattern)
            )
        )

    return query

def getAllAnnouncementsIsDeleteFalse(session: Session, search: str, page: int):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .join(Class, onclause=(Announcement.class_id == Class.id))
        .where(Announcement.is_delete == False)
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements

def getAllAnnouncementsByTeacherAndIsDeleteFalse(teacherId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .join(Class, onclause=(Announcement.class_id == Class.id), isouter=True)
        .where(
            Announcement.is_delete == False,
            (Class.supervisor_id == teacherId) | (Announcement.class_id == None)
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements

def getAllAnnouncementsByStudentAndIsDeleteFalse(studentId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .join(Class, onclause=(Class.id == Announcement.class_id), isouter=True)
        .join(Student, onclause=(Class.id == Student.class_id))
        .where(
            Announcement.is_delete == False,
            (Student.id == studentId) | (Announcement.class_id == None)
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements

def getAllAnnouncementsByParentAndIsDeleteFalse(parentId, session, search, page):
    offset_value = (page - 1) * settings.ITEMS_PER_PAGE

    query = (
        select(Announcement)
        .join(Class, onclause=(Class.id == Announcement.class_id))
        .join(Student, onclause=(Class.id == Student.class_id))
        .where(
            Announcement.is_delete == False,
            (Student.parent_id == parentId) | (Announcement.class_id == None)
        )
    )

    query = addSearchOption(query, search)
    query = query.offset(offset_value).limit(settings.ITEMS_PER_PAGE)
    announcements = session.exec(query).unique().all()
    return announcements