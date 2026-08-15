from pathlib import Path
import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("ONPONTO_DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'onponto.db'}")
UPLOADS_DIR = Path(os.getenv("ONPONTO_UPLOADS_DIR", BACKEND_DIR / "uploads"))

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def habilitar_chaves_estrangeiras(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
