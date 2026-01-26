import uuid
from typing import List
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AdminUser, TeacherOrAdminUser, AllUser
from repository.parent import getAllParentIsDeleteFalse, countParent, parentSave, parentUpdate, parentSoftDelete, \
    getParentById
from schemas import ParentRead, SaveResponse, ParentSave, ParentUpdate, PaginatedParentResponse

router = APIRouter(
    prefix="/parent",
)


@router.get("/count", response_model=int)
def register(current_user: AdminUser, session: SessionDep):
    return countParent(session)


@router.get("/getAll", response_model=PaginatedParentResponse)
def getAllParent(current_user: TeacherOrAdminUser, session: SessionDep, search: str = None, page: int = 1):
    all_parents = getAllParentIsDeleteFalse(session, search, page)
    return all_parents


@router.get("/getById/{parentId}", response_model=ParentRead)
def getById(current_user: AllUser, parentId: uuid.UUID, session: SessionDep):
    parent_detail = getParentById(parentId, session)

    if not parent_detail:
        raise HTTPException(
            status_code=404,
            detail="Parent not found with provided ID."
        )

    return parent_detail


@router.post("/save", response_model=SaveResponse)
def saveParent(parent: ParentSave, current_user: AdminUser, session: SessionDep):
    if not parent.username or len(parent.username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not parent.first_name or len(parent.first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not parent.last_name or len(parent.last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not parent.email:
        raise HTTPException(
            status_code=400,
            detail="Email is required."
        )

    if not parent.phone or len(parent.phone.strip()) != 10:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be exactly 10 digits."
        )

    if not parent.phone.strip().isdigit():
        raise HTTPException(
            status_code=400,
            detail="Phone number must contain only digits."
        )

    if not parent.address or len(parent.address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    result = parentSave(parent, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateParent(current_user: AdminUser, parent: ParentUpdate, session: SessionDep):
    if not parent.id:
        raise HTTPException(
            status_code=400,
            detail="Parent ID is required for updating."
        )

    if not parent.username or len(parent.username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not parent.first_name or len(parent.first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not parent.last_name or len(parent.last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not parent.email:
        raise HTTPException(
            status_code=400,
            detail="Email is required."
        )

    if not parent.phone or len(parent.phone.strip()) != 10:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be exactly 10 digits."
        )

    if not parent.phone.strip().isdigit():
        raise HTTPException(
            status_code=400,
            detail="Phone number must contain only digits."
        )

    if not parent.address or len(parent.address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    result = parentUpdate(parent, session)
    return result


@router.delete("/delete", response_model=SaveResponse)
def softDeleteParent(current_user: AdminUser, id: uuid.UUID, session: SessionDep):
    if id is None:
        raise HTTPException(
            status_code=400,
            detail="Parent ID is required for deleting."
        )

    result = parentSoftDelete(id, session)
    return result
