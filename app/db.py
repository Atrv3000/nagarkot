"""Database connection, session management, SQLite WAL setup, and audit immutability triggers."""
import os
import sqlite3
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nagarkot.db")

# Enable foreign keys and WAL mode for all SQLite connections
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine=None):
    """Create all tables and register immutability triggers on audit_log."""
    import app.models  # Ensure all models are registered on Base.metadata
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    # SQLite append-only triggers for audit_log
    with eng.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS audit_log_no_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'Audit log is append-only: UPDATE prohibited');
            END;
        """)
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'Audit log is append-only: DELETE prohibited');
            END;
        """)
        conn.commit()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
