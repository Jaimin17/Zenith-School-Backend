import uuid
from token import STRING
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AdminUser
from repository.subject import getAllSubjectsIsDeleteFalse, subjectSave, SubjectUpdate, SubjectSoftDelete_with_lesson, \
    findSubjectById
from schemas import SubjectRead, SubjectBase, SubjectSave, SubjectSaveResponse, SubjectUpdateBase

router = APIRouter(
    prefix="/subject",
)


@router.get("/getAll", response_model=List[SubjectRead])
def getAllSubject(current_user: AdminUser, session: SessionDep, search: str = None, page: int = 1):
    all_subjects = getAllSubjectsIsDeleteFalse(session, search, page)
    return all_subjects


@router.get("/get/{subjectId}", response_model=SubjectRead)
def getSubjectById(current_user: AdminUser, subjectId: uuid.UUID, session: SessionDep):
    if subjectId is None:
        raise HTTPException(status_code=400, detail="Subject ID is not present.")

    result = findSubjectById(subjectId, session)
    return result


@router.post("/save", response_model=SubjectSaveResponse)
def saveSubject(current_user: AdminUser, subject: SubjectSave, session: SessionDep):
    if subject.name is None or len(subject.name) <= 1:
        raise HTTPException(status_code=400, detail="Invalid subject name. Should be greater than 1 char.")

    result = subjectSave(subject, session)
    return result


@router.put("/update", response_model=SubjectSaveResponse)
def updateSubject(current_user: AdminUser, data: SubjectUpdateBase, session: SessionDep):
    if not data.id:
        raise HTTPException(
            status_code=400,
            detail="Subject ID is required for updating."
        )

    if not data.name or len(data.name.strip()) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Subject name must be at least 2 characters long."
        )

    result = SubjectUpdate(data, session)
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
