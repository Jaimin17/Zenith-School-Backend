from sqlalchemy import func
from sqlmodel import Session, select

from models import Admin


def countAdmin(session: Session):
    return session.exec(
        select(func.count()).select_from(Admin).where(Admin.is_delete == False)
    ).first()