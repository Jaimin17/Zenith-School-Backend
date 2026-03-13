import uuid
from typing import List, Optional

from fastapi.params import Form

from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AllUser, StudentOrTeacherOrAdminUser, AdminUser, ParentUser
from models import Day
from repository.lesson import getAllLessonIsDeleteFalse, getAllLessonOfTeacherIsDeleteFalse, \
    getAllLessonOfClassIsDeleteFalse, getAllLessonOfParentIsDeleteFalse, countAllLessonOfTeacher, \
    countAllLessonOfStudent, lessonSave, lessonUpdate, lessonSoftDelete, getLessonById, \
    getAllLessonOfCurrentWeekIsDeleteFalse, getAllLessonOfTeacherOfCurrentWeekIsDeleteFalse, \
    getAllLessonOfClassOfCurrentWeekIsDeleteFalse, getAllLessonOfStudentOfCurrentWeekIsDeleteFalse, \
    getAllLessonList, getAllLessonsOfTeacherByYear, getAllLessonsOfClassByYear, getAllLessonsByYear
from schemas import LessonRead, SaveResponse, LessonSave, LessonUpdate, LessonDeleteResponse, PaginatedLessonResponse
from datetime import datetime

router = APIRouter(
    prefix="/lesson",
)


def validate_lesson_data(
        name: str,
        day: str,
        start_time: str,
        end_time: str,
        subject_id: str,
        class_id: str,
        teacher_id: str,
        lesson_id: Optional[str] = None
) -> dict:
    """
    Validate and parse lesson form data.
    Returns a dict with parsed values or raises HTTPException.
    """
    # Validate lesson ID (for updates)
    if lesson_id:
        try:
            parsed_id = uuid.UUID(lesson_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Lesson ID is not a valid UUID."
            )
    else:
        parsed_id = None

    # Validate name
    if not name or len(name.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Lesson name is required and must be at least 3 characters long."
        )

    # Validate day
    if not day or day.capitalize() not in Day:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid day. Must be one of: {', '.join(Day)}"
        )
    else:
        selectedDay = Day[day.upper()]

    # Validate and parse start time
    if not start_time:
        raise HTTPException(
            status_code=400,
            detail="Start time is required."
        )

    try:
        # Try HH:MM format first
        starting_time = datetime.strptime(start_time, "%H:%M").time()
    except ValueError:
        try:
            # Try HH:MM:SS format
            starting_time = datetime.strptime(start_time, "%H:%M:%S").time()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Start time must be in HH:MM or HH:MM:SS format."
            )

    # Validate and parse end time
    if not end_time:
        raise HTTPException(
            status_code=400,
            detail="End time is required."
        )

    try:
        # Try HH:MM format first
        ending_time = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        try:
            # Try HH:MM:SS format
            ending_time = datetime.strptime(end_time, "%H:%M:%S").time()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="End time must be in HH:MM or HH:MM:SS format."
            )

    # Validate time order
    if starting_time >= ending_time:
        raise HTTPException(
            status_code=400,
            detail="Lesson start time must be before end time."
        )

    # Validate subject ID
    if not subject_id:
        raise HTTPException(
            status_code=400,
            detail="Subject is required."
        )
    try:
        subject_uuid = uuid.UUID(subject_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Subject ID is not a valid UUID."
        )

    # Validate class ID
    if not class_id:
        raise HTTPException(
            status_code=400,
            detail="Class is required."
        )
    try:
        class_uuid = uuid.UUID(class_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Class ID is not a valid UUID."
        )

    # Validate teacher ID
    if not teacher_id:
        raise HTTPException(
            status_code=400,
            detail="Teacher is required."
        )
    try:
        teacher_uuid = uuid.UUID(teacher_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Teacher ID is not a valid UUID."
        )

    return {
        "id": parsed_id,
        "name": name.strip(),
        "day": selectedDay,
        "start_time": starting_time,
        "end_time": ending_time,
        "subject_id": subject_uuid,
        "class_id": class_uuid,
        "teacher_id": teacher_uuid,
    }


@router.get("/getAll", response_model=PaginatedLessonResponse)
def getAllLesson(current_user: AllUser, session: SessionDep, search: str = None, page: int = 1,
                academic_year_id: Optional[uuid.UUID] = None):
    user, role = current_user
    if role == "admin":
        all_lessons = getAllLessonIsDeleteFalse(session, search, page, academic_year_id)
    elif role == "teacher":
        all_lessons = getAllLessonOfTeacherIsDeleteFalse(user.id, session, search, page, academic_year_id=academic_year_id)
    elif role == "student":
        all_lessons = getAllLessonOfClassIsDeleteFalse(user.class_id, session, search, page, academic_year_id)
    else:
        all_lessons = getAllLessonOfParentIsDeleteFalse(user.id, session, search, page, academic_year_id)
    return all_lessons

@router.get("/getFullList", response_model=List[LessonRead])
def getFullListLesson(current_user: AllUser, session: SessionDep):
    user, role = current_user
    all_lessons = getAllLessonList(session)
    return all_lessons


@router.get("/getAllOfCurrentWeek", response_model=List[LessonRead])
def getAllOfCurrentWeek(current_user: StudentOrTeacherOrAdminUser, session: SessionDep):
    user, role = current_user

    if role == "admin":
        all_lessons = getAllLessonOfCurrentWeekIsDeleteFalse(session)
    elif role == "teacher":
        all_lessons = getAllLessonOfTeacherOfCurrentWeekIsDeleteFalse(user.id, session)
    else:
        all_lessons = getAllLessonOfClassOfCurrentWeekIsDeleteFalse(user.class_id, session)

    return all_lessons


@router.get("/getLessonForStudent/{studentId}", response_model=List[LessonRead])
def getLessonForStudent(studentId: uuid.UUID, current_user: AllUser, session: SessionDep):
    user, role = current_user

    all_lessons = getAllLessonOfStudentOfCurrentWeekIsDeleteFalse(studentId, user, role, session)

    return all_lessons


@router.get("/getById/{lessonId}", response_model=LessonRead)
def getById(lessonId: uuid.UUID, current_user: AllUser, session: SessionDep):
    user, role = current_user

    lesson_detail = getLessonById(lessonId, session)

    if not lesson_detail:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found with provided ID."
        )

    if role.lower() == "admin":
        return lesson_detail

    elif role.lower() == "teacher":
        if lesson_detail.teacher_id and lesson_detail.teacher_id == user.id:
            return lesson_detail
        elif lesson_detail.related_class and lesson_detail.related_class.supervisor_id == user.id:
            return lesson_detail
        else:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this Lesson."
            )

    elif role.lower() == "student":
        if lesson_detail.related_class is None:
            raise HTTPException(
                status_code=500,
                detail="Lesson class data is missing."
            )

        class_students = [s.id for s in lesson_detail.related_class.students if not s.is_delete]
        if user.id not in class_students:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this lesson."
            )

        return lesson_detail

    elif role.lower() == "parent":
        if lesson_detail.related_class is None:
            raise HTTPException(
                status_code=500,
                detail="Lesson class data is missing."
            )

        if not user.students:
            raise HTTPException(
                status_code=403,
                detail="No students associated with your account."
            )

        class_student_ids = [s.id for s in lesson_detail.related_class.students if not s.is_delete]
        parent_student_ids = [s.id for s in user.students if not s.is_delete]

        # Check if any of parent's students are in the class
        has_access = any(student_id in class_student_ids for student_id in parent_student_ids)

        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="None of your children have access to this lesson."
            )

        return lesson_detail

    else:
        raise HTTPException(
            status_code=403,
            detail="Invalid user role."
        )


@router.get("/teacher/{teacherId}", response_model=PaginatedLessonResponse)
def getLessonOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                       page: int = 1):
    all_lessons = getAllLessonOfTeacherIsDeleteFalse(teacherId, session, search, page)
    return all_lessons


@router.get("/teacher/weekly/{teacherId}", response_model=List[LessonRead])
def getAllLessonOfTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    all_lessons = getAllLessonOfTeacherIsDeleteFalse(teacherId, session, None, 1, False)
    return all_lessons


@router.get("/countByTeacher/{teacherId}", response_model=int)
def countLessonByTeacher(teacherId: uuid.UUID, current_user: CurrentUser, session: SessionDep):
    total_lessons = countAllLessonOfTeacher(teacherId, session)
    return total_lessons


@router.get("/countByStudent/{studentId}", response_model=int)
def countLessonByStudent(studentId: uuid.UUID, current_user: StudentOrTeacherOrAdminUser, session: SessionDep):
    total_lesson = countAllLessonOfStudent(studentId, session)
    return total_lesson


@router.get("/class/{classId}", response_model=PaginatedLessonResponse)
def getAllLessonOfClass(classId: uuid.UUID, current_user: CurrentUser, session: SessionDep, search: str = None,
                        page: int = 1):
    all_lessons = getAllLessonOfClassIsDeleteFalse(classId, session, search, page)
    return all_lessons


@router.get("/getAllByYear", response_model=List[LessonRead])
def getAllLessonsByAcademicYear(
    academic_year_id: uuid.UUID,
    current_user: StudentOrTeacherOrAdminUser,
    session: SessionDep,
):
    """Return all lessons for a given academic year, filtered by the caller's role."""
    from models import StudentClassHistory
    from sqlmodel import select as _select
    user, role = current_user
    if role == "admin":
        return getAllLessonsByYear(academic_year_id, session)
    elif role == "teacher":
        return getAllLessonsOfTeacherByYear(user.id, academic_year_id, session)
    else:  # student
        history = session.exec(
            _select(StudentClassHistory).where(
                StudentClassHistory.student_id == user.id,
                StudentClassHistory.academic_year_id == academic_year_id,
            )
        ).first()
        if not history or not history.class_id:
            return []
        return getAllLessonsOfClassByYear(history.class_id, academic_year_id, session)


@router.post("/save", response_model=SaveResponse)
def saveLesson(
        current_user: AdminUser,
        session: SessionDep,
        name: str = Form(...),
        day: str = Form(...),
        start_time: str = Form(...),
        end_time: str = Form(...),
        subject_id: str = Form(...),
        class_id: str = Form(...),
        teacher_id: str = Form(...),
):
    validated_data = validate_lesson_data(
        name=name,
        day=day,
        start_time=start_time,
        end_time=end_time,
        subject_id=subject_id,
        class_id=class_id,
        teacher_id=teacher_id,
    )

    # Create lesson object
    lesson_data = LessonSave(
        name=validated_data["name"],
        day=validated_data["day"],
        start_time=validated_data["start_time"],
        end_time=validated_data["end_time"],
        subject_id=validated_data["subject_id"],
        class_id=validated_data["class_id"],
        teacher_id=validated_data["teacher_id"],
    )

    result = lessonSave(lesson_data, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateLesson(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        name: str = Form(...),
        day: str = Form(...),
        start_time: str = Form(...),
        end_time: str = Form(...),
        subject_id: str = Form(...),
        class_id: str = Form(...),
        teacher_id: str = Form(...),
):
    validated_data = validate_lesson_data(
        name=name,
        day=day,
        start_time=start_time,
        end_time=end_time,
        subject_id=subject_id,
        class_id=class_id,
        teacher_id=teacher_id,
        lesson_id=id,
    )

    # Create lesson object
    lesson_data = LessonUpdate(
        id=validated_data["id"],
        name=validated_data["name"],
        day=validated_data["day"],
        start_time=validated_data["start_time"],
        end_time=validated_data["end_time"],
        subject_id=validated_data["subject_id"],
        class_id=validated_data["class_id"],
        teacher_id=validated_data["teacher_id"],
    )

    result = lessonUpdate(lesson_data, session)
    return result


@router.delete("/delete", response_model=LessonDeleteResponse)
def softDeleteLesson(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    result = lessonSoftDelete(id, session)
    return result
