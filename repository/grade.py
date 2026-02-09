from sqlmodel import Session, select

from models import Grade


def getAllGradesIsDeleteFalse(session: Session):
    query = (
        select(Grade)
        .where(
            Grade.is_delete == False
        )
    )

    query = query.order_by(Grade.level)

    all_grades = session.exec(query).all()

    return all_grades
