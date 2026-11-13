from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def create_engine_from_url(database_url: str, echo: bool = False) -> Engine:
    return create_engine(
        database_url,
        echo=echo,
        connect_args={"check_same_thread": False},
    )


def create_session_factory(database_url: str, echo: bool = False) -> sessionmaker[Session]:
    engine_instance = create_engine_from_url(database_url, echo=echo)
    return sessionmaker(
        bind=engine_instance,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


settings = get_settings()
engine = create_engine_from_url(settings.database_url, echo=settings.database_echo)
SessionLocal = create_session_factory(settings.database_url, echo=settings.database_echo)
rules_engine = create_engine_from_url(settings.rules_database_url, echo=settings.database_echo)
RulesSessionLocal = create_session_factory(settings.rules_database_url, echo=settings.database_echo)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_rules_db() -> Generator[Session, None, None]:
    db = RulesSessionLocal()
    try:
        yield db
    finally:
        db.close()
