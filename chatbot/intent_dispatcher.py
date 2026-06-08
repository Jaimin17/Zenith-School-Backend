"""
intent_dispatcher.py

First-pass routing layer for the /chatbot/sql-query endpoint.
Tries to answer the query via existing repository functions
(no LLM call needed).  Falls back to LLM-SQL generation only
when no existing API covers the detected entity type.

Flow:
  1. detect_entity_type()  – keyword match, returns entity string or None
  2. dispatch()            – calls the right repo function for the role
  3. Caller falls back to classify_and_generate_query() if None returned
"""

import uuid
from datetime import date
from typing import Any
from sqlmodel import Session

# ── Entity keyword registry ───────────────────────────────────────
# Each key is the entity type; each value is a list of substrings
# that unambiguously indicate that entity.
# Pad the query with spaces before matching to avoid false substring
# hits (e.g. "test" inside "latest" — handled by the space padding).
_ENTITY_KEYWORDS: dict[str, list[str]] = {
    "attendance":    [" attendance", " absent", " present", " tardy", " late "],
    "exams":         [" exam", " quiz ", " test "],
    "assignments":   [" assignment", " homework", " task ", " due date", " due on"],
    "results":       [" result", " score", " mark ", " grade ", " performance", " passed", " failed"],
    "announcements": [" announcement", " notice ", " circular", " notification"],
    "events":        [" event ", " activity ", " function ", " ceremony"],
    "lessons":       [" lesson", " schedule", " timetable", " class period", " class time"],
    "students":      ["student list", "students in class", "students of class", "class members", "who is in"],
}


def detect_entity_type(query: str) -> str | None:
    """
    Returns the detected entity type or None if no keyword matches.
    Pads query with spaces so keywords don't false-match mid-word.
    """
    padded = f" {query.lower()} "
    for entity, keywords in _ENTITY_KEYWORDS.items():
        if any(kw in padded for kw in keywords):
            return entity
    return None


# ── Parameter helpers ─────────────────────────────────────────────

def _resolve_year_id(extra: dict) -> uuid.UUID | None:
    year_str = str(extra.get("selected_academic_year_id", "")).strip()
    if year_str and year_str.lower() not in {"", "undefined", "null"}:
        try:
            return uuid.UUID(year_str)
        except ValueError:
            pass
    return None


def _to_dicts(paginated: Any) -> list[dict]:
    """Convert a paginated Pydantic response to a list of plain dicts.
    Prepends a _meta entry with total_count so the LLM knows if
    there is more data beyond the first page."""
    if not paginated or not hasattr(paginated, "data"):
        return []
    items: list[dict] = [item.model_dump(mode="json") for item in paginated.data]
    if hasattr(paginated, "total_count") and paginated.total_count is not None:
        items.insert(0, {
            "_meta_total": paginated.total_count,
            "_meta_page": getattr(paginated, "page", 1),
            "_meta_total_pages": getattr(paginated, "total_pages", 1),
        })
    return items


# ── Main dispatch entry point ─────────────────────────────────────

def dispatch(
    entity_type: str,
    user: Any,
    role: str,
    session: Session,
    extra: dict,
) -> list[dict] | None:
    """
    Route to the right repository function.
    Returns list of dicts on success, None if no handler or on error
    (caller should fall back to LLM-SQL in that case).
    """
    year_id = _resolve_year_id(extra)
    try:
        if entity_type == "exams":
            return _get_exams(user, role, session, year_id)
        if entity_type == "assignments":
            return _get_assignments(user, role, session, year_id)
        if entity_type == "results":
            return _get_results(user, role, session, year_id)
        if entity_type == "attendance":
            return _get_attendance(user, role, session)
        if entity_type == "announcements":
            return _get_announcements(user, role, session)
        if entity_type == "events":
            return _get_events(user, role, session)
        if entity_type == "lessons":
            return _get_lessons(user, role, session, year_id)
        if entity_type == "students":
            return _get_students(user, role, session, year_id)
    except Exception:
        pass  # any error → let caller try LLM-SQL
    return None


# ── Per-entity handlers ───────────────────────────────────────────

def _get_exams(user, role: str, session: Session, year_id: uuid.UUID | None) -> list[dict]:
    from repository.exams import (
        getAllExamsIsDeleteFalse,
        getAllExamsOfTeacherIsDeleteFalse,
        getAllExamsOfStudentIsDeleteFalse,
        getAllExamsOfParentIsDeleteFalse,
    )
    if role == "student":
        result = getAllExamsOfStudentIsDeleteFalse(user.id, session, "", 1, year_id)
    elif role == "teacher":
        result = getAllExamsOfTeacherIsDeleteFalse(user.id, session, "", 1, year_id)
    elif role == "parent":
        result = getAllExamsOfParentIsDeleteFalse(user.id, session, "", 1, year_id)
    else:
        result = getAllExamsIsDeleteFalse(session, "", 1, year_id)
    return _to_dicts(result)


def _get_assignments(user, role: str, session: Session, year_id: uuid.UUID | None) -> list[dict]:
    from repository.assignments import (
        getAllAssignmentsIsDeleteFalse,
        getAllAssignmentsOfTeacherIsDeleteFalse,
        getAllAssignmentsOfStudentIsDeleteFalse,
        getAllAssignmentsOfParentIsDeleteFalse,
    )
    if role == "student":
        result = getAllAssignmentsOfStudentIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    elif role == "teacher":
        result = getAllAssignmentsOfTeacherIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    elif role == "parent":
        result = getAllAssignmentsOfParentIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    else:
        result = getAllAssignmentsIsDeleteFalse(
            session, "", 1, academic_year_id=year_id
        )
    return _to_dicts(result)


def _get_results(user, role: str, session: Session, year_id: uuid.UUID | None) -> list[dict]:
    from repository.results import (
        getAllResultsIsDeleteFalse,
        getAllResultsByTeacherIsDeleteFalse,
        getAllResultsOfStudentIsDeleteFalse,
        getAllResultsOfParentIsDeleteFalse,
    )
    if role == "student":
        result = getAllResultsOfStudentIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    elif role == "teacher":
        result = getAllResultsByTeacherIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    elif role == "parent":
        result = getAllResultsOfParentIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    else:
        result = getAllResultsIsDeleteFalse(session, "", 1, academic_year_id=year_id)
    return _to_dicts(result)


def _get_attendance(user, role: str, session: Session) -> list[dict]:
    today = date.today()
    if role == "student":
        from repository.attendance import attendanceOfStudentOfCurrentYear
        rows = attendanceOfStudentOfCurrentYear(user.id, today.replace(month=1, day=1), session)
        return [
            r.model_dump(mode="json") if hasattr(r, "model_dump") else
            {"attendance_date": str(r.attendance_date), "status": str(r.status)}
            for r in rows
        ]
    elif role == "teacher":
        from repository.attendance import getTeacherClasses
        result = getTeacherClasses(user.id, today, session)
        return [result.model_dump(mode="json")] if hasattr(result, "model_dump") else []
    elif role == "parent":
        from repository.attendance import getParentChildrenAttendance
        results = getParentChildrenAttendance(user.id, today.year, today.month, session)
        return [r.model_dump(mode="json") for r in results] if isinstance(results, list) else []
    else:  # admin
        from repository.attendance import getDashboardSummary
        result = getDashboardSummary(today, session)
        return [result.model_dump(mode="json")] if hasattr(result, "model_dump") else []


def _get_announcements(user, role: str, session: Session) -> list[dict]:
    from repository.announcements import (
        getAllAnnouncementsIsDeleteFalse,
        getAllAnnouncementsByTeacherAndIsDeleteFalse,
        getAllAnnouncementsByStudentAndIsDeleteFalse,
        getAllAnnouncementsByParentAndIsDeleteFalse,
    )
    if role == "student":
        result = getAllAnnouncementsByStudentAndIsDeleteFalse(user.id, session)
    elif role == "teacher":
        result = getAllAnnouncementsByTeacherAndIsDeleteFalse(user.id, session)
    elif role == "parent":
        result = getAllAnnouncementsByParentAndIsDeleteFalse(user.id, session)
    else:
        result = getAllAnnouncementsIsDeleteFalse(session, "", 1)
    return _to_dicts(result)


def _get_events(user, role: str, session: Session) -> list[dict]:
    from repository.events import (
        getAllEventsIsDeleteFalse,
        getAllEventsByTeacherAndIsDeleteFalse,
        getAllEventsByStudentAndIsDeleteFalse,
        getAllEventsByParentAndIsDeleteFalse,
    )
    if role == "student":
        result = getAllEventsByStudentAndIsDeleteFalse(user.id, session, "", 1)
    elif role == "teacher":
        result = getAllEventsByTeacherAndIsDeleteFalse(user.id, session, "", 1)
    elif role == "parent":
        result = getAllEventsByParentAndIsDeleteFalse(user.id, session, "", 1)
    else:
        result = getAllEventsIsDeleteFalse(session, "", 1)
    return _to_dicts(result)


def _get_lessons(user, role: str, session: Session, year_id: uuid.UUID | None) -> list[dict]:
    if role == "student":
        from repository.lesson import getAllLessonOfStudentOfCurrentWeekIsDeleteFalse
        rows = getAllLessonOfStudentOfCurrentWeekIsDeleteFalse(user.id, user, role, session)
        if isinstance(rows, list):
            return [
                r.model_dump(mode="json") if hasattr(r, "model_dump") else dict(r)
                for r in rows
            ]
        return []
    elif role == "teacher":
        from repository.lesson import getAllLessonOfTeacherIsDeleteFalse
        result = getAllLessonOfTeacherIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    elif role == "parent":
        from repository.lesson import getAllLessonOfParentIsDeleteFalse
        result = getAllLessonOfParentIsDeleteFalse(
            user.id, session, "", 1, academic_year_id=year_id
        )
    else:
        from repository.lesson import getAllLessonIsDeleteFalse
        result = getAllLessonIsDeleteFalse(session, "", 1, year_id)
    return _to_dicts(result)


def _get_students(user, role: str, session: Session, year_id: uuid.UUID | None) -> list[dict]:
    if role == "teacher":
        from repository.student import getAllStudentsOfTeacherAndIsDeleteFalse
        result = getAllStudentsOfTeacherAndIsDeleteFalse(session, user.id, "", 1, year_id)
        return _to_dicts(result)
    elif role == "admin":
        from repository.student import getAllStudentsIsDeleteFalse
        result = getAllStudentsIsDeleteFalse(session, "", 1, year_id)
        return _to_dicts(result)
    return []  # student/parent don't query class member lists
