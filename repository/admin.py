from typing import Optional

from fastapi import HTTPException
from psycopg import IntegrityError
from sqlalchemy import func
from sqlmodel import Session, select

from core.security import get_password_hash
from models import Admin
from schemas import updatePasswordModel


def countAdmin(session: Session):
    return session.exec(
        select(func.count()).select_from(Admin).where(Admin.is_delete == False)
    ).first()


def updateAdminPassword(data: updatePasswordModel, session: Session):
    query = (
        select(Admin)
        .where(
            Admin.is_delete == False,
            Admin.id == data.id
        )
    )

    current_user: Optional[Admin] = session.exec(query).first()

    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    updatedHashPassword = get_password_hash(data.password)

    current_user.password = updatedHashPassword
    session.add(current_user)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error while updating password."
        )

    return "Password updated successfully"
