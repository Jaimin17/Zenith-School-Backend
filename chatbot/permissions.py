import uuid

# This defines what tables/info each role can access
# LLM will only be allowed to query within these boundaries

ROLE_PERMISSIONS = {
    "student": {
        "allowed_tables": ["attendance", "result", "lesson", "exam", "assignment", "announcement", "event"],
        "scope": "own_data",  # only their own records
        "description": "a student who can only see their own grades, attendance, schedule and announcements"
    },
    "teacher": {
        "allowed_tables": ["lesson", "exam", "assignment", "attendance", "result", "announcement", "event", "student"],
        "scope": "class_data",  # students in their classes only
        "description": "a teacher who can see their lessons, their students' data, exams and assignments they created"
    },
    "parent": {
        "allowed_tables": ["attendance", "result", "lesson", "announcement", "event"],
        "scope": "child_data",  # only their child's records
        "description": "a parent who can only see their child's grades, attendance and school announcements"
    },
    "admin": {
        "allowed_tables": ["all"],
        "scope": "all_data",
        "description": "an admin who can see all school data including all students, teachers, classes and results"
    }
}


def get_user_permission_context(role: str, user_id: uuid.UUID, extra: dict) -> dict:
    """Returns permission info to inject into LLM prompt."""
    perm = ROLE_PERMISSIONS.get(role, {})

    context = {
        "role": role,
        "user_id": str(user_id),
        "scope": perm.get("scope"),
        "allowed_tables": perm.get("allowed_tables", []),
        "description": perm.get("description", ""),
        "extra": extra,
    }

    return context
