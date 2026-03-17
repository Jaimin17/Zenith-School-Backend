
from fastapi import APIRouter, status
from typing import List
from uuid import UUID

from core.database import SessionDep
from deps import AdminUser, AllUser
from schemas import HolidayCreate, HolidayRead, HolidayUpdate
from repository import holiday as repository_holiday

router = APIRouter()

@router.post('/', response_model=HolidayRead, status_code=status.HTTP_201_CREATED)
def create_holiday(holiday: HolidayCreate, db: SessionDep, current_user: AdminUser):
    return repository_holiday.create_holiday(holiday, db)

@router.get('/', response_model=List[HolidayRead])
def get_holidays(db: SessionDep, current_user: AllUser, skip: int = 0, limit: int = 100):
    return repository_holiday.get_holidays(db, skip, limit)

@router.patch('/{holiday_id}', response_model=HolidayRead)
def update_holiday(holiday_id: UUID, holiday: HolidayUpdate, db: SessionDep, current_user: AdminUser):
    return repository_holiday.update_holiday(holiday_id, holiday, db)

@router.delete('/{holiday_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(holiday_id: UUID, db: SessionDep, current_user: AdminUser):
    return repository_holiday.delete_holiday(holiday_id, db)

