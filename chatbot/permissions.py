# app/chatbot/permissions.py

import uuid

ROLE_PERMISSIONS = {
    "student": {
        "allowed_tables": [
            "student", "attendance", "result", "lesson",
            "exam", "assignment", "announcement", "event",
            "class", "grade", "subject", "academic_year", "student_class_history",
            "holiday", "banner",
        ],
        "scope": "own_data",
        "description": "student",
    },
    "teacher": {
        "allowed_tables": [
            "teacher", "lesson", "exam", "assignment", "attendance",
            "result", "student", "class", "subject",
            "teacher_subject_link", "announcement", "event", "grade",
            "academic_year", "student_class_history", "holiday", "banner",
        ],
        "scope": "class_data",
        "description": "teacher",
    },
    "parent": {
        "allowed_tables": [
            "parent", "student", "attendance", "result", "lesson",
            "exam", "assignment", "announcement", "event", "class", "grade", "subject",
            "academic_year", "student_class_history", "holiday", "banner",
        ],
        "scope": "child_data",
        "description": "parent",
    },
    "admin": {
        "allowed_tables": [
            "student", "teacher", "parent", "admin",
            "class", "grade", "subject", "teacher_subject_link",
            "lesson", "exam", "assignment",
            "result", "attendance", "announcement", "event",
            "academic_year", "student_class_history", "holiday", "banner",
        ],
        "scope": "all_data",
        "description": "admin",
    },
}


def get_user_permission_context(role: str, user_id: uuid.UUID, extra: dict) -> dict:
    """
    Builds the permission context dict injected into classifier prompts.

    Args:
        role:     'student' | 'teacher' | 'parent' | 'admin'
        user_id:  UUID of the logged-in user
        extra:    e.g. {'child_id': '...'} pre-resolved for parent role

    Returns:
        Dict with role, user_id, scope, allowed_tables, description, extra
    """
    perm = ROLE_PERMISSIONS.get(role)

    if not perm:
        return {
            "role": "unknown",
            "user_id": str(user_id),
            "scope": "no_access",
            "allowed_tables": [],
            "description": "unknown",
            "extra": extra,
        }

    return {
        "role": role,
        "user_id": str(user_id),
        "scope": perm["scope"],
        "allowed_tables": perm["allowed_tables"],
        "description": perm["description"],
        "extra": extra,
    }
