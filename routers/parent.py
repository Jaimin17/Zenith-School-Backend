import uuid
from typing import List

from fastapi.params import Form

from core.config import settings
from core.database import SessionDep
from fastapi import APIRouter, HTTPException
from deps import CurrentUser, AdminUser, TeacherOrAdminUser, AllUser
from repository.parent import getAllParentIsDeleteFalse, countParent, parentSave, parentUpdate, parentSoftDelete, \
    getParentById, getFullListOfParentsIsDeleteFalse
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


@router.get("/getFullList", response_model=List[ParentRead])
def getFullListOfParents(current_user: AdminUser, session: SessionDep):
    all_parents = getFullListOfParentsIsDeleteFalse(session)
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
def saveParent(
        current_user: AdminUser,
        session: SessionDep,
        username: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        address: str = Form(...),
        password: str = Form(...)
):
    if not username or len(username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not first_name or len(first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not last_name or len(last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not settings.EMAIL_RE.match(email.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format."
        )

    if not phone or len(phone.strip()) != 10:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be exactly 10 digits."
        )

    if not password.strip() or len(password.strip()) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password is Required. And should be at least 6 characters long."
        )

    if not settings.PHONE_RE.match(phone.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid Indian phone number. Must be 10 digits starting with 6-9."
        )

    if not address or len(address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    parent_data: ParentSave = ParentSave(
        username=username.strip(),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        phone=phone.strip(),
        address=address.strip(),
        password=password.strip()
    )

    result = parentSave(parent_data, session)
    return result


@router.put("/update", response_model=SaveResponse)
def updateParent(
        current_user: AdminUser,
        session: SessionDep,
        id: str = Form(...),
        username: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        address: str = Form(...),
):
    if not id:
        raise HTTPException(
            status_code=400,
            detail="Parent ID is required for updating."
        )

    if not username or len(username.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username is required and must be at least 3 characters long."
        )

    if not first_name or len(first_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="First name is required."
        )

    if not last_name or len(last_name.strip()) < 1:
        raise HTTPException(
            status_code=400,
            detail="Last name is required."
        )

    if not settings.EMAIL_RE.match(email.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format."
        )

    if not settings.PHONE_RE.match(phone.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid Indian phone number. Must be 10 digits starting with 6-9."
        )

    if not address or len(address.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 10 characters long."
        )

    parent_data: ParentUpdate = ParentUpdate(
        id=uuid.UUID(id),
        username=username.strip(),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        phone=phone.strip(),
        address=address.strip(),
        password=None
    )

    result = parentUpdate(parent_data, session)
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
