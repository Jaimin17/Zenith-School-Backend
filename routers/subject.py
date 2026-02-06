import uuid
from token import STRING
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException, Form
from deps import CurrentUser, AdminUser, TeacherOrAdminUser
from repository.subject import getAllSubjectsIsDeleteFalse, subjectSave, SubjectUpdate, SubjectSoftDelete_with_lesson, \
    findSubjectById, countSubjectForTeacher, getListOfAllSubjectIsDeleteFalse
from schemas import SubjectRead, SubjectBase, SubjectSave, SubjectSaveResponse, SubjectUpdateBase, \
    PaginatedSubjectResponse

router = APIRouter(
    prefix="/subject",
)


@router.get("/getAll", response_model=PaginatedSubjectResponse)
def getAllSubject(current_user: AdminUser, session: SessionDep, search: str = None, page: int = 1):
    all_subjects = getAllSubjectsIsDeleteFalse(session, search, page)
    return all_subjects


@router.get("/getFullList", response_model=List[SubjectBase])
def getFullListOfSubject(current_user: TeacherOrAdminUser, session: SessionDep):
    all_subjects = getListOfAllSubjectIsDeleteFalse(session)
    return all_subjects


@router.get("/get/{subjectId}", response_model=SubjectRead)
def getSubjectById(current_user: AdminUser, subjectId: uuid.UUID, session: SessionDep):
    if subjectId is None:
        raise HTTPException(status_code=400, detail="Subject ID is not present.")

    result = findSubjectById(subjectId, session)
    return result


@router.get("/countByTeacher/{teacherId}", response_model=int)
def subjectCountForTeacher(current_user: TeacherOrAdminUser, teacherId: uuid.UUID, session: SessionDep):
    totalSubjects = countSubjectForTeacher(teacherId, session)
    return totalSubjects


@router.post("/save", response_model=SubjectSaveResponse)
def saveSubject(
        current_user: AdminUser,
        session: SessionDep,
        name: str = Form(...),
        teachers: List[str] = Form(...),
):
    if name is None or len(name) <= 1:
        raise HTTPException(status_code=400, detail="Invalid subject name. Should be greater than 1 char.")

    try:
        teacher_ids = [
            uuid.UUID(s.strip())
            for s in teachers
            if s.strip()
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subject UUID format: {str(e)}"
        )

    subject_data: SubjectSave = SubjectSave(
        name=name.strip(),
        teachersList=teacher_ids,
    )

    result = subjectSave(subject_data, session)
    return result


@router.put("/update", response_model=SubjectSaveResponse)
def updateSubject(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        name: str = Form(...),
        teachers: List[str] = Form(...),
):
    if not id:
        raise HTTPException(
            status_code=400,
            detail="Subject ID is required for updating."
        )

    if not name or len(name.strip()) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Subject name must be at least 2 characters long."
        )

    try:
        teacher_ids = [
            uuid.UUID(s.strip())
            for s in teachers
            if s.strip()
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subject UUID format: {str(e)}"
        )

    subject_data: SubjectUpdateBase = SubjectUpdateBase(
        id=uuid.UUID(id),
        name=name.strip(),
        teachersList=teacher_ids,
    )

    result = SubjectUpdate(subject_data, session)
    return result


@router.delete("/delete", response_model=SubjectSaveResponse)
def softDeleteSubject(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Subject ID is required for deleting."
        )

    result = SubjectSoftDelete_with_lesson(id, session)
    return result
