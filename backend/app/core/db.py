from contextlib import contextmanager
from typing import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

# Create database engine
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28
from app.models import Item, User  # noqa: F401


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Get a database session context manager.

    This is used for background tasks that need database access
    outside of FastAPI's dependency injection.

    Usage:
        with get_session() as session:
            session.exec_statement(select(User)).all()
    """
    with Session(engine) as session:
        yield session
