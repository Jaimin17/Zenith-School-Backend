from typing import Generator, Annotated

from fastapi.params import Depends

from .config import Settings
from sqlmodel import create_engine, Session, SQLModel

settings = Settings()

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), echo=True)

def init_db(session: Session) -> None:
    SQLModel.metadata.create_all(engine)

def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_db)]