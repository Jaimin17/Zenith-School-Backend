from sqlmodel import Session, select
from fastapi import HTTPException, status
from typing import List
from uuid import UUID
from datetime import date

from models import Holiday
from schemas import HolidayCreate, HolidayRead, HolidayUpdate

def create_holiday(holiday_data: HolidayCreate, db: Session) -> Holiday:
    # Check if holiday exists
    existing = db.exec(select(Holiday).where(Holiday.date == holiday_data.date)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Holiday already exists on this date")
    
    holiday = Holiday(**holiday_data.dict())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday

def get_holidays(db: Session, skip: int = 0, limit: int = 100) -> List[Holiday]:
    return db.exec(select(Holiday).order_by(Holiday.date.desc()).offset(skip).limit(limit)).all()

def update_holiday(holiday_id: UUID, holiday_data: HolidayUpdate, db: Session) -> Holiday:
    holiday = db.get(Holiday, holiday_id)
    if not holiday:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
        
    update_data = holiday_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key != "id":
            setattr(holiday, key, value)
            
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday

def delete_holiday(holiday_id: UUID, db: Session):
    holiday = db.get(Holiday, holiday_id)
    if not holiday:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
        
    db.delete(holiday)
    db.commit()
    return {"message": "Holiday deleted successfully"}
